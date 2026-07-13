const BASE = "/api";

export async function fetchChats({ cursor, search } = {}) {
	const params = new URLSearchParams();
	if (cursor) params.set("cursor", cursor);
	if (search) params.set("search", search);
	const qs = params.toString();
	const url = qs ? `${BASE}/chats?${qs}` : `${BASE}/chats`;
	const res = await fetch(url);
	if (!res.ok) throw new Error(`Failed to fetch chats: ${res.status}`);
	return res.json();
}

export async function fetchChatMessages(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/messages`);
	if (!res.ok) throw new Error(`Failed to fetch messages: ${res.status}`);
	return res.json();
}

export async function createChat() {
	const res = await fetch(`${BASE}/chats`, { method: "POST" });
	if (!res.ok) throw new Error(`Failed to create chat: ${res.status}`);
	return res.json();
}

export async function forkChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/fork`, { method: "POST" });
	if (!res.ok) throw new Error(`Failed to fork chat: ${res.status}`);
	return res.json();
}

export async function endChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/end`, { method: "POST" });
	if (!res.ok) throw new Error(`Failed to end chat: ${res.status}`);
	return res.json();
}

export async function reactivateChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/reactivate`, {
		method: "POST",
	});
	if (!res.ok) throw new Error(`Failed to reactivate chat: ${res.status}`);
	return res.json();
}

export async function deleteChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}`, { method: "DELETE" });
	if (!res.ok) throw new Error(`Failed to delete chat: ${res.status}`);
	return res.json();
}

export async function fetchDocuments({ status } = {}) {
	const params = new URLSearchParams();
	if (status) params.set("status", status);
	const qs = params.toString();
	const url = qs ? `${BASE}/documents?${qs}` : `${BASE}/documents`;
	const res = await fetch(url);
	if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
	return res.json();
}

export async function uploadDocumentFile(file, onProgress) {
	const formData = new FormData();
	formData.append("file", file);

	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		xhr.open("POST", `${BASE}/documents/upload`);
		xhr.withCredentials = true;

		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable && onProgress) {
				onProgress((e.loaded / e.total) * 100);
			}
		};

		xhr.onload = () => {
			if (xhr.status >= 200 && xhr.status < 300) {
				try {
					resolve(JSON.parse(xhr.responseText));
				} catch (e) {
					reject(new Error("Invalid response"));
				}
			} else {
				reject(new Error(`Upload failed: ${xhr.status}`));
			}
		};

		xhr.onerror = () => reject(new Error("Network error"));
		xhr.send(formData);
	});
}

export async function deleteDocument(docId) {
	const res = await fetch(`${BASE}/documents/${docId}`, { method: "DELETE" });
	if (!res.ok) throw new Error(`Failed to delete document: ${res.status}`);
	return res.json();
}

export async function fetchMemories() {
	const res = await fetch(`${BASE}/memories`);
	if (!res.ok) throw new Error(`Failed to fetch memories: ${res.status}`);
	return res.json();
}

export async function deleteMemory(memoryId) {
	const res = await fetch(`${BASE}/memories/${memoryId}`, { method: "DELETE" });
	if (!res.ok) throw new Error(`Failed to delete memory: ${res.status}`);
	return res.json();
}

export async function fetchStats() {
	const res = await fetch(`${BASE}/stats`);
	if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`);
	return res.json();
}
