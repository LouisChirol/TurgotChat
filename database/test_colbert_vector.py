import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

# Load environment variables
load_dotenv()


def test_colbert_vector():
    # Initialize embeddings and vector store
    embeddings = MistralAIEmbeddings(
        model="mistral-embed", api_key=os.getenv("MISTRAL_API_KEY")
    )

    vector_store = Chroma(
        collection_name="service_public",
        embedding_function=embeddings,
        persist_directory="chroma_db",
    )

    # Initialize Mistral chat model
    llm = ChatMistralAI(
        model="mistral-large-latest", api_key=os.getenv("MISTRAL_API_KEY")
    )

    # Create a prompt template
    template = """Tu es Colbert, un assistant virtuel du service public français. 
    Utilise les informations suivantes pour répondre à la question de l'utilisateur.
    Si tu ne trouves pas la réponse dans les documents fournis, dis-le clairement.
    
    Documents pertinents:
    {context}
    
    Question: {question}
    
    Réponse:"""

    prompt = ChatPromptTemplate.from_template(template)

    # Test query
    test_query = "Comment obtenir un permis de construire ?"
    print(f"\nQuestion: {test_query}")

    # Get relevant documents
    docs = vector_store.similarity_search(test_query, k=3)
    context = "\n\n".join([doc.page_content for doc in docs])

    # Generate response
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": test_query})

    print("\nRéponse de Colbert:")
    print(response.content)

    print("\nDocuments utilisés:")
    for i, doc in enumerate(docs, 1):
        print(f"\n--- Document {i} ---")
        print(f"Source: {doc.metadata.get('source', 'N/A')}")
        print(f"Type: {doc.metadata.get('type', 'N/A')}")


if __name__ == "__main__":
    test_colbert_vector()
