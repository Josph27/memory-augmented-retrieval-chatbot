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

export async function endChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/end`, { method: "POST" });
	if (!res.ok) throw new Error(`Failed to end chat: ${res.status}`);
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
