import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.markdown("""
<style>
.stTextInput>div>div>input {
    font-size: 16px;
}
.stButton button {
    border-radius: 8px;
    padding: 8px 16px;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="AI News Assistant", layout="centered")

st.title("🧠 AI News Assistant")
st.write("Ask anything about current news")

query = st.text_input("Enter your question")

if st.button("📰 Show Top Headlines"):
    response = requests.get(f"{API_URL}/top-news")
    data = response.json()

    st.subheader("Top News")

    for article in data:
        st.markdown(f"- [{article['title']}]({article['url']})")
        
if st.button("Ask"):

    if query:
        with st.spinner("Thinking..."):
            try:
                response = requests.get(
                    f"{API_URL}/ask",
                    params={"query": query}
                )

                data = response.json()

                if "answer" in data:
                    st.subheader("🧠 Answer")
                    st.markdown(data["answer"])

                    if "sources" in data:
                        st.subheader("📚 Sources")
                        for i, source in enumerate(data["sources"], 1):
                            st.markdown(f"### {i}. [{source['title']}]({source['url']})")

                            if source.get("image"):
                                st.image(source["image"], use_column_width=True)

                            st.markdown("---")
                else:
                    st.error(data)

            except Exception as e:
                st.error(str(e))