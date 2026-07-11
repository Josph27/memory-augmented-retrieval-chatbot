import { useParams } from "react-router-dom";
import ChainlitChat from "../components/ChainlitChat";

export default function Chat() {
	const { chatId } = useParams();
	return (
		<div
			style={{
				height: "calc(100vh - 3rem)",
				overscrollBehavior: "none",
				paddingBottom: "2rem",
			}}
		>
			<ChainlitChat chatId={chatId} />
		</div>
	);
}
