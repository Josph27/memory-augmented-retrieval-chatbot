const BASE = "/api";

/** Extract a meaningful error message from a non-ok fetch response. */
async function _apiError(res, fallback) {
	try {
		const body = await res.json();
		if (body && body.error) return body.error;
		if (body && body.detail) return body.detail;
	} catch {}
	return `${fallback} (HTTP ${res.status})`;
}

export async function fetchChats({ cursor, search } = {}) {
	const params = new URLSearchParams();
	if (cursor) params.set("cursor", cursor);
	if (search) params.set("search", search);
	const qs = params.toString();
	const url = qs ? `${BASE}/chats?${qs}` : `${BASE}/chats`;
	const res = await fetch(url);
	if (!res.ok) throw new Error(await _apiError(res, "Failed to fetch chats"));
	return res.json();
}

export async function fetchChatMessages(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/messages`);
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to fetch messages"));
	return res.json();
}

export async function createChat() {
	const res = await fetch(`${BASE}/chats`, { method: "POST" });
	if (!res.ok) throw new Error(await _apiError(res, "Failed to create chat"));
	return res.json();
}

export async function forkChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/fork`, { method: "POST" });
	if (!res.ok) throw new Error(await _apiError(res, "Failed to fork chat"));
	return res.json();
}

export async function endChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/end`, { method: "POST" });
	if (!res.ok) throw new Error(await _apiError(res, "Failed to end chat"));
	return res.json();
}

export async function reactivateChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/reactivate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to reactivate chat"));
	return res.json();
}

export async function deleteChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}`, { method: "DELETE" });
	if (!res.ok) throw new Error(await _apiError(res, "Failed to delete chat"));
	return res.json();
}

export async function consolidateChat(chatId) {
	const res = await fetch(`${BASE}/chats/${chatId}/consolidate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to consolidate chat"));
	return res.json();
}

export async function fetchDocuments({ status } = {}) {
	const params = new URLSearchParams();
	if (status) params.set("status", status);
	const qs = params.toString();
	const url = qs ? `${BASE}/documents?${qs}` : `${BASE}/documents`;
	const res = await fetch(url);
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to fetch documents"));
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
				reject(new Error(`Upload failed (HTTP ${xhr.status})`));
			}
		};

		xhr.onerror = () =>
			reject(new Error("Network error — is the backend running?"));
		xhr.send(formData);
	});
}

export async function deleteDocument(docId) {
	const res = await fetch(`${BASE}/documents/${docId}`, { method: "DELETE" });
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to delete document"));
	return res.json();
}

export async function deactivateDocument(docId) {
	const res = await fetch(`${BASE}/documents/${docId}/deactivate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to deactivate document"));
	return res.json();
}

export async function activateDocument(docId) {
	const res = await fetch(`${BASE}/documents/${docId}/activate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to activate document"));
	return res.json();
}

export async function fetchMemories({ status } = {}) {
	const params = new URLSearchParams();
	if (status) params.set("status", status);
	const qs = params.toString();
	const url = qs ? `${BASE}/memories?${qs}` : `${BASE}/memories`;
	const res = await fetch(url);
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to fetch memories"));
	return res.json();
}

export async function deactivateMemory(memoryId) {
	const res = await fetch(`${BASE}/memories/${memoryId}/deactivate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to deactivate memory"));
	return res.json();
}

export async function activateMemory(memoryId) {
	const res = await fetch(`${BASE}/memories/${memoryId}/activate`, {
		method: "POST",
	});
	if (!res.ok)
		throw new Error(await _apiError(res, "Failed to activate memory"));
	return res.json();
}

export async function deleteMemory(memoryId) {
	const res = await fetch(`${BASE}/memories/${memoryId}`, { method: "DELETE" });
	if (!res.ok) throw new Error(await _apiError(res, "Failed to delete memory"));
	return res.json();
}

export async function fetchStats() {
	const res = await fetch(`${BASE}/stats`);
	if (!res.ok) throw new Error(await _apiError(res, "Failed to fetch stats"));
	return res.json();
}
