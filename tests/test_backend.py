from src.database import Database
from src.config import AppConfig
from src.model_wrapper import ModelWrapper
from src.chat_service import ChatService
import uuid


def main():
    config = AppConfig.from_env()
    db = Database(config.database_path)
    model = ModelWrapper(config, model_name=config.model_name)
    chat_service = ChatService(
        database=db, model=model, raw_message_limit=10, memory_update_batch_size=5
    )

    chat_id = str(uuid.uuid4())
    db.create_chat(chat_id)

    print("Testing handle_user_turn...")
    try:
        res = chat_service.handle_user_turn(chat_id, "What is 2+2?", orchestration_mode="native")
        print("Success:", res.answer)
    except Exception:
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
