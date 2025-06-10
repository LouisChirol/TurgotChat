import os
import random

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_mistralai import MistralAIEmbeddings

# Load environment variables
load_dotenv()


def test_vector_db():
    # Initialize embeddings
    embeddings = MistralAIEmbeddings(
        model="mistral-embed", api_key=os.getenv("MISTRAL_API_KEY")
    )

    # Load the existing vector store
    vector_store = Chroma(
        collection_name="service_public",
        embedding_function=embeddings,
        persist_directory="chroma_db",
    )

    # Get collection info
    collection = vector_store._collection
    count = collection.count()
    print(f"\nTotal documents in database: {count}")

    if count == 0:
        print("No documents found in the database!")
        return

    # Get a random document
    random_id = random.randint(0, count - 1)
    random_doc = collection.get(ids=[collection.get()['ids'][random_id]])
    print("\nRandom document from database:")
    print(f"ID: {random_doc['ids'][0]}")
    print(f"Content: {random_doc['documents'][0][:500]}...")  # First 500 chars
    print(f"Metadata: {random_doc['metadatas'][0]}")

    # Test query
    test_query = "Comment obtenir un permis de construire ?"
    print(f"\nTesting query: {test_query}")

    # Get similar documents
    docs = vector_store.similarity_search(test_query, k=3)

    print("\nFound similar documents:")
    for i, doc in enumerate(docs, 1):
        print(f"\n--- Document {i} ---")
        print(f"Content: {doc.page_content[:200]}...")  # First 200 chars
        print(f"Metadata: {doc.metadata}")


if __name__ == "__main__":
    test_vector_db()
