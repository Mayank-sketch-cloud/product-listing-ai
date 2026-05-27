import streamlit as st
import base64
import json
import os
import re
import csv
import io
from datetime import datetime
from PIL import Image
import hashlib

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

st.set_page_config(page_title="ProductListingAI", page_icon="🚀", layout="wide")

# ============ USER AUTHENTICATION ============
def make_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

if "users" not in st.session_state:
    st.session_state.users = {"demo@example.com": make_hash("demo123")}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None

def login_page():
    st.markdown("""
    <style>
    .login-container { max-width: 400px; margin: 0 auto; padding: 40px; background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); margin-top: 60px; }
    .login-title { font-size: 2rem; font-weight: 800; text-align: center; background: linear-gradient(90deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 20px; }
    .feature-box { background: #f8f9ff; border-radius: 12px; padding: 20px; margin: 10px; text-align: center; }
    .feature-icon { font-size: 2.5rem; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🚀 ProductListingAI</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center;color:#666;margin-bottom:30px;">Upload product photos. AI creates listings for Meesho, Amazon & Flipkart.</p>', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if email in st.session_state.users and st.session_state.users[email] == make_hash(password):
                    st.session_state.logged_in = True
                    st.session_state.current_user = email
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        with tab2:
            new_email = st.text_input("Email", key="signup_email")
            new_pass = st.text_input("Password", type="password", key="signup_pass")
            confirm_pass = st.text_input("Confirm Password", type="password", key="signup_confirm")
            if st.button("Create Account", use_container_width=True):
                if new_pass != confirm_pass:
                    st.error("Passwords don't match")
                elif len(new_pass) < 6:
                    st.error("Password must be 6+ characters")
                elif new_email in st.session_state.users:
                    st.error("Email already exists")
                else:
                    st.session_state.users[new_email] = make_hash(new_pass)
                    st.session_state.logged_in = True
                    st.session_state.current_user = new_email
                    st.success("Account created!")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;margin-bottom:20px;'>How It Works</h3>", unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        with f1:
            st.markdown('<div class="feature-box"><div class="feature-icon">📸</div><h4>Upload Photo</h4><p>Take a photo of your product</p></div>', unsafe_allow_html=True)
        with f2:
            st.markdown('<div class="feature-box"><div class="feature-icon">🤖</div><h4>AI Analyzes</h4><p>Detects color, material, style</p></div>', unsafe_allow_html=True)
        with f3:
            st.markdown('<div class="feature-box"><div class="feature-icon">📋</div><h4>Get Listings</h4><p>Ready for all platforms</p></div>', unsafe_allow_html=True)


# ============ AI PROMPT ============
VISION_PROMPT = """You are a senior e-commerce catalog analyst with 10 years experience on Indian marketplaces (Meesho, Amazon India, Flipkart, Myntra).

STEP 1 - IDENTIFY CATEGORY:
A. MEN'S CLOTHING (Shirt, T-Shirt, Jeans, Trousers, Kurta, Jacket, Blazer, Sweater, Hoodie, Vest, Innerwear)
B. WOMEN'S CLOTHING (Kurta, Saree, Dress, Top, T-Shirt, Jeans, Leggings, Skirt, Jacket, Sweater, Hoodie, Nightwear)
C. MOBILE ACCESSORIES (Case, Cover, Screen Guard, Charger, Cable, Earphones, Power Bank)
D. HOME & KITCHEN (Container, Bottle, Cookware, Organizer, Decor, Bedding, Towel)
E. FOOTWEAR (Casual Shoes, Formal Shoes, Sports Shoes, Sandals, Slippers, Boots, Sneakers, Loafers)
F. OTHER (Specify exact category)

STEP 2 - DEEP VISUAL ANALYSIS:
For CLOTHING: garment type, primary color (Indian terms: Mustard, Maroon, Teal, Rust), secondary colors, pattern (Solid/Striped/Checked/Floral/Printed/Embroidered), fabric texture (Cotton weave/Silk sheen/Polyester smooth/Denim/Linen/Wool/Knitted), sleeve (Full/Half/3-4/Sleeveless/Cap), collar/neck (Spread/Mandarin/Round/V-Neck/Henley/Off-shoulder/Halter), fit (Slim/Regular/Loose/Oversized), length, hem, closure, pockets, embellishments, occasion, gender.
For MOBILE: accessory type, compatible brand/model, material (TPU/Silicone/Polycarbonate/Leather/Metal), finish, design, features, color, pattern.
For HOME: item type, material, capacity, pieces, lid type, shape, features, color, pattern, dimensions.
For FOOTWEAR: type, upper/sole material, closure, toe shape, heel, occasion, features, color.

STEP 3 - READ ALL VISIBLE TEXT:
Brand names, size tags, material composition percentages, care instructions, model numbers, capacity markings, price tags, country, certification marks (ISI, ISO, BIS, CE, FCC).

STEP 4 - CONFIDENCE SCORING:
0.95-1.00: Clearly visible. 0.80-0.94: Some ambiguity. 0.60-0.79: Partially visible. Below 0.60: Flag as uncertain.

STEP 5 - GENERATE LISTINGS using ONLY detected attributes. Never invent.

SELLER INPUT: MRP: Rs.{mrp}, Selling Price: Rs.{selling_price}, Quantity: {quantity}, Platforms: {platforms}

MEESHO: Title max 100 chars [Gender][Pattern][Material][Product][Feature]. Description 2-3 paragraphs. 5 bullet points. 20-30 keywords with Hindi. HSN correct. GST 5% clothing<1000, 12% clothing>1000, 18% electronics.
AMAZON: Title max 200 chars Title Case [Brand][Model][Product][Feature][Color]. HTML description. 5 bullets ALL CAPS lead word. Backend keywords max 250 chars.
FLIPKART: Title max 150 chars [Fit][Fabric][Pattern][Product][Color]. 2 paragraphs. Key highlights attribute-value. Map all attributes.

OUTPUT ONLY JSON:
{"detected_category":"","confidence_score":0,"visual_analysis":{"primary_color":"","secondary_colors":[],"pattern":"","material_texture":"","material_composition":"","visible_text":[],"brand":"","design_features":[],"product_category":"","sub_category":""},"category_attributes":{"sleeve":"","collar_neck":"","fit":"","length":"","closure":"","pockets":"","occasion":"","gender":""},"meesho":{"title":"","description":"","bullet_points":[],"keywords":"","hsn_code":"","gst_percent":5,"weight_kg":"","size":"","color_family":""},"amazon":{"title":"","description":"","bullet_points":[],"backend_keywords":"","browse_node":"","item_type_keyword":"","variation_theme":""},"flipkart":{"title":"","description":"","key_highlights":[],"vertical":"","category":"","attributes":{}},"compliance_flags":[{"level":"","message":"","attribute":""}]}

FINAL RULE: If confidence below 0.70, FLAG IT. Never present low-confidence data as fact."""


def analyze_with_openai(image_bytes, mrp, selling_price, quantity, platforms, api_key):
    client = openai.OpenAI(api_key=api_key)
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = VISION_PROMPT.format(mrp=mrp, selling_price=selling_price, quantity=quantity, platforms=platforms)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
        ]}],
        max_tokens=4000,
        temperature=0.15
    )

    content = response.choices[0].message.content
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return json.loads(content)
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return json.loads(content[start:end+1])
    raise ValueError("No valid JSON in AI response")


def generate_meesho_csv(data, mrp, sp, qty):
    meesho = data.get("meesho", {})
    visual = data.get("visual_analysis", {})
    attrs = data.get("category_attributes", {})
    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["Product Name","SKU","Description","MRP","Selling Price","Quantity","Category","Weight (kg)","HSN Code","GST Percentage","Main Image URL","Size","Color","Fabric","Pattern","Sleeve Type","Neck Type","Fit","Occasion","Brand"]
    sku = f"SKU-{datetime.now().strftime('%H%M%S')}"
    row = [meesho.get("title",""), sku, meesho.get("description","").replace("\n"," "), f"{float(mrp):.2f}", f"{float(sp):.2f}", qty, "Men > Clothing > Shirts", meesho.get("weight_kg","0.300"), meesho.get("hsn_code","6205"), meesho.get("gst_percent",5), "", meesho.get("size","M, L, XL, XXL"), visual.get("primary_color",""), visual.get("material_composition",attrs.get("fabric","")), visual.get("pattern",""), attrs.get("sleeve",""), attrs.get("collar_neck",""), attrs.get("fit",""), attrs.get("occasion",""), visual.get("brand","Generic")]
    writer.writerow(headers)
    writer.writerow(row)
    return output.getvalue()


# ============ MAIN APP ============
if not st.session_state.logged_in:
    login_page()
else:
    st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; background: linear-gradient(90deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub-title { color: #666; font-size: 1rem; margin-bottom: 1.5rem; }
    .detected-box { background: linear-gradient(135deg, #f8f9ff, #fff8f0); border: 2px solid #e0e4ff; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }
    .attr-card { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 0.75rem; }
    .attr-label { font-size: 0.75rem; color: #888; text-transform: uppercase; }
    .attr-value { font-weight: 700; color: #333; font-size: 1rem; }
    .platform-title { font-size: 1.2rem; font-weight: 700; color: #667eea; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e4ff; }
    .conf-high { color: #2e7d32; font-weight: 700; }
    .conf-med { color: #ef6c00; font-weight: 700; }
    .conf-low { color: #c62828; font-weight: 700; }
    .stButton>button { background: linear-gradient(135deg, #667eea, #764ba2); color: white; font-weight: 700; border: none; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown('<div class="main-title">🚀 ProductListingAI</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Upload product photos. AI creates listings for Meesho, Amazon & Flipkart.</div>', unsafe_allow_html=True)
    with col_h2:
        st.write("")
        st.write("")
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.rerun()
        st.caption(f"Logged in as: {st.session_state.current_user}")

    if not OPENAI_AVAILABLE:
        st.error("Install openai: pip install openai")
        st.stop()

    api_key = st.text_input("🔑 OpenAI API Key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    if not api_key:
        st.info("Enter your OpenAI API key. Get one at platform.openai.com/api-keys")
        st.stop()

    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        st.success("✅ API Key valid! Ready to analyze.")
    except:
        st.error("Invalid API Key")
        st.stop()

    st.divider()

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("📸 Product Input")
        uploaded = st.file_uploader("Upload product photo", type=["jpg", "jpeg", "png", "webp"])
        if uploaded:
            st.image(uploaded, use_container_width=True)

        c1, c2 = st.columns(2)
        mrp = c1.number_input("MRP (Rs.)", min_value=1, value=999, step=10)
        sp = c2.number_input("Selling Price (Rs.)", min_value=1, value=499, step=10)
        qty = st.number_input("Stock", min_value=0, value=50, step=5)

        if sp >= mrp:
            st.warning("Selling Price must be less than MRP")

        st.markdown("**Platforms**")
        p1, p2, p3 = st.columns(3)
        pm = p1.checkbox("Meesho", True)
        pa = p2.checkbox("Amazon", True)
        pf = p3.checkbox("Flipkart", True)
        platforms = []
        if pm: platforms.append("meesho")
        if pa: platforms.append("amazon")
        if pf: platforms.append("flipkart")

        btn = st.button("✨ Analyze with AI", disabled=not uploaded or sp >= mrp or len(platforms) == 0, use_container_width=True)

    with col2:
        st.subheader("📋 AI Results")

        if not uploaded:
            st.info("Upload an image to start")

        if btn and uploaded:
            with st.spinner("🔍 AI analyzing image... 10-20 seconds"):
                try:
                    img_bytes = uploaded.getvalue()
                    result = analyze_with_openai(img_bytes, mrp, sp, qty, ", ".join(platforms), api_key)
                    st.session_state.result = result
                    st.session_state.mrp = mrp
                    st.session_state.sp = sp
                    st.session_state.qty = qty
                except Exception as e:
                    st.error(f"Failed: {e}")
                    st.info("Try a clearer image or check API key balance")

        if "result" in st.session_state and st.session_state.result:
            r = st.session_state.result
            conf = r.get("confidence_score", 0)
            conf_class = "conf-high" if conf > 0.85 else "conf-med" if conf > 0.6 else "conf-low"
            conf_text = "High Confidence" if conf > 0.85 else "Medium - Review" if conf > 0.6 else "Low - Verify"

            st.markdown(f'<div class="detected-box"><div style="font-size: 1.2rem; font-weight: 700;">{r.get("detected_category", "Unknown")}</div><div class="{conf_class}">{int(conf*100)}% - {conf_text}</div></div>', unsafe_allow_html=True)

            visual = r.get("visual_analysis", {})
            st.markdown("### 🔍 Detected from Image")

            cols = st.columns(2)
            items = [("Color", visual.get("primary_color", "N/A")), ("Material", visual.get("material_composition", visual.get("material_texture", "N/A"))), ("Pattern", visual.get("pattern", "N/A")), ("Brand", visual.get("brand", "N/A"))]
            for i, (label, val) in enumerate(items):
                with cols[i % 2]:
                    st.markdown(f'<div class="attr-card"><div class="attr-label">{label}</div><div class="attr-value">{val}</div></div>', unsafe_allow_html=True)

            texts = visual.get("visible_text", [])
            if texts:
                st.markdown("**📖 Text Read:** " + " - ".join([f"`{t}`" for t in texts]))

            features = visual.get("design_features", [])
            if features:
                st.markdown("**✨ Features:** " + ", ".join(features))

            attrs = r.get("category_attributes", {})
            if any(v for v in attrs.values() if v):
                st.markdown("### 📐 Details")
                acols = st.columns(3)
                for i, (k, v) in enumerate(attrs.items()):
                    if v:
                        with acols[i % 3]:
                            st.markdown(f'<div class="attr-card"><div class="attr-label">{k.replace("_", " ").title()}</div><div class="attr-value">{v}</div></div>', unsafe_allow_html=True)

            flags = r.get("compliance_flags", [])
            if flags:
                st.markdown("### ⚠️ Review")
                for f in flags:
                    level = f.get("level", "info")
                    msg = f.get("message", "")
                    if level == "warning": st.warning(msg)
                    elif level == "error": st.error(msg)
                    else: st.info(msg)

            st.divider()

            if "meesho" in r and pm:
                st.markdown('<div class="platform-title">🛒 Meesho</div>', unsafe_allow_html=True)
                m = r["meesho"]
                t = st.text_area("Title", m.get("title", ""), height=70)
                st.caption(f"{len(t)}/100 chars")
                st.text_area("Description", m.get("description", ""), height=120)
                st.markdown("**Bullets:**")
                for i, bp in enumerate(m.get("bullet_points", [])[:5]):
                    st.text_input(f"{i+1}", bp, key=f"mb{i}")
                st.text_area("Keywords", m.get("keywords", ""), height=60)
                if st.button("📥 Meesho CSV", key="mc"):
                    csv = generate_meesho_csv(r, st.session_state.mrp, st.session_state.sp, st.session_state.qty)
                    st.download_button("Download", csv, f"meesho_{datetime.now().strftime('%H%M%S')}.csv", "text/csv")

            if "amazon" in r and pa:
                st.markdown('<div class="platform-title">📦 Amazon</div>', unsafe_allow_html=True)
                a = r["amazon"]
                t = st.text_area("Title", a.get("title", ""), height=70, key="at")
                st.caption(f"{len(t)}/200 chars")
                st.text_area("Description", a.get("description", ""), height=150, key="ad")
                st.markdown("**Bullets:**")
                for i, bp in enumerate(a.get("bullet_points", [])[:5]):
                    st.text_input(f"{i+1}", bp, key=f"ab{i}")
                st.text_area("Keywords", a.get("backend_keywords", ""), height=60, key="ak")

            if "flipkart" in r and pf:
                st.markdown('<div class="platform-title">🛍️ Flipkart</div>', unsafe_allow_html=True)
                f = r["flipkart"]
                t = st.text_area("Title", f.get("title", ""), height=70, key="ft")
                st.caption(f"{len(t)}/150 chars")
                st.text_area("Description", f.get("description", ""), height=120, key="fd")
                st.markdown("**Highlights:**")
                for i, hl in enumerate(f.get("key_highlights", [])[:6]):
                    st.text_input(f"{i+1}", hl, key=f"fh{i}")
                attrs = f.get("attributes", {})
                if attrs:
                    st.markdown("**Attributes:**")
                    fcols = st.columns(3)
                    for i, (k, v) in enumerate(attrs.items()):
                        with fcols[i % 3]:
                            st.text_input(k, v, key=f"fa{k}")

    st.divider()
    st.caption("ProductListingAI - GPT-4o Vision - Built for Indian E-commerce Sellers")
