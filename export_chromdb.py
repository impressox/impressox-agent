import chromadb
import json

# Khởi tạo PersistentClient mới theo chuẩn
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("rag_data")

# Lấy toàn bộ dữ liệu
results = collection.get(include=["documents", "metadatas", "embeddings"])

# Chuẩn bị dữ liệu để export
export_data = []
for i in range(len(results["ids"])):
    export_data.append({
        "id": results["ids"][i],
        "text": results["documents"][i],
        "metadata": results["metadatas"][i]
        # Nếu cần embeddings: "embedding": results["embeddings"][i]
    })

# Ghi ra JSON
with open("chroma_export.json", "w", encoding="utf-8") as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2)

print("✅ Export thành công → chroma_export.json")
