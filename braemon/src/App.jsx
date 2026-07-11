import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Chats from "./pages/Chats";
import Documents from "./pages/Documents";
import Memories from "./pages/Memories";
import Diagnostics from "./pages/Diagnostics";

function App() {
	return (
		<BrowserRouter>
			<Routes>
				<Route element={<Layout />}>
					<Route path="/" element={<Home />} />
					<Route path="/chat/:chatId?" element={<Chat />} />
					<Route path="/chats" element={<Chats />} />
					<Route path="/documents" element={<Documents />} />
					<Route path="/memories" element={<Memories />} />
					<Route path="/diagnostics" element={<Diagnostics />} />
				</Route>
			</Routes>
		</BrowserRouter>
	);
}

export default App;
