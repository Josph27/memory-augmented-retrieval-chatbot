import { RecoilRoot } from "recoil";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ChainlitProvider from "./components/ChainlitProvider";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Chats from "./pages/Chats";
import Documents from "./pages/Documents";
import Memories from "./pages/Memories";

function App() {
	return (
		<RecoilRoot>
			<ChainlitProvider>
				<BrowserRouter>
					<Routes>
						<Route element={<Layout />}>
							<Route path="/" element={<Home />} />
							<Route path="/chat/:chatId?" element={<Chat />} />
							<Route path="/chats" element={<Chats />} />
							<Route path="/documents" element={<Documents />} />
							<Route path="/memories" element={<Memories />} />
						</Route>
					</Routes>
				</BrowserRouter>
			</ChainlitProvider>
		</RecoilRoot>
	);
}

export default App;
