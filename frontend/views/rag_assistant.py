from __future__ import annotations

import streamlit as st
import pandas as pd
from api_client import query_rag, ingest_document, get_documents


def render_rag_assistant() -> None:
    st.subheader("RAG Knowledge Assistant")
    st.caption("Search clinical frameworks, treatment worksheets, and safety protocols indexed in the knowledge base.")

    role = st.session_state.get("user_role")
    
    # 1. Search Query
    st.markdown("### Search Therapist Guidelines")
    query = st.text_input("Enter research question or clinical topic", value="How do we support anxiety and sleep problems?")
    
    if st.button("Search Knowledge Base"):
        if not query.strip():
            st.warning("Please enter a query.")
            return
            
        with st.spinner("Analyzing semantic document indices..."):
            res = query_rag(query)
            
        if res:
            st.markdown("#### Clinical Synthesis")
            st.write(res["answer"])
            
            # Display matching source details
            sources = res.get("sources", [])
            if sources:
                st.write("")
                st.markdown("#### Matching Document Excerpts")
                for src in sources:
                    st.markdown(
                        f'<div class="compact-card" style="border-left: 4px solid #10b981;">'
                        f'<b>Source:</b> {src["title"]} | <b>Cosine Similarity Score:</b> {src["score"]}<br/>'
                        f'<p style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem;">{src["excerpt"]}...</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        else:
            st.error("Failed to query knowledge assistant. Verify backend connection.")

    st.markdown("---")
    
    # 2. Document Library & Ingestion (RBAC Restricted)
    if role in {"Admin", "Psychologist", "Assistant"}:
        st.markdown("### Clinical Library Management")
        
        # Upload tool
        st.markdown("#### Ingest New Document")
        upload = st.file_uploader("Upload guidance document (TXT, MD, PDF, DOCX)", type=["txt", "md", "pdf", "docx"])
        if upload is not None:
            if st.button("Index Document"):
                with st.spinner(f"Ingesting {upload.name}..."):
                    success = ingest_document(upload.getvalue(), upload.name)
                if success:
                    st.success(f"Successfully ingested and indexed \"{upload.name}\"!")
                    st.rerun()
                else:
                    st.error(f"Failed to ingest \"{upload.name}\". File must contain readable text.")
                    
        # List of indexed documents
        st.write("")
        st.markdown("#### Currently Indexed Guidelines")
        docs = get_documents()
        if docs:
            df = pd.DataFrame(docs)
            display_df = df[["id", "name", "size_kb", "uploaded_at"]].copy()
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No guidelines are indexed. Upload a protocol document above to populate the clinical library.")
    else:
        st.info("Note: Clinical library document ingestion is restricted to administrators and psychologist accounts.")
