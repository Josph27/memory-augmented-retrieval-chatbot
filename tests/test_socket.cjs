const { io } = require("socket.io-client");

const socket = io("http://localhost:8000", {
	path: "/ws/socket.io",
	transports: ["websocket"],
});

socket.on("connect", () => {
	console.log("Connected to Chainlit Socket.IO");

	const message = {
		id: "test-id-1234",
		type: "user_message",
		name: "user",
		output: "Hello from socket.io-client!",
		createdAt: new Date().toISOString(),
	};

	socket.emit("client_message", { message, fileReferences: [] });
	console.log("Sent client_message");
});

socket.on("task_start", () => console.log("Received: task_start"));
socket.on("task_end", () => {
	console.log("Received: task_end");
	process.exit(0);
});
socket.on("stream_start", (step) =>
	console.log("Received: stream_start", step.id),
);
socket.on("stream_token", (token) =>
	console.log("Received: stream_token", token.token),
);
socket.on("new_message", (msg) =>
	console.log("Received: new_message", msg.id, msg.output?.substring(0, 50)),
);

setTimeout(() => {
	console.log("Timeout");
	process.exit(1);
}, 20000);
