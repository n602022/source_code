import unittest

from chatbot import ask_chatbot


class AskChatbotTests(unittest.TestCase):
    def test_unrelated_question_is_rejected(self):
        self.assertEqual(
            ask_chatbot("câu hỏi không liên quan"),
            "Chưa đủ tài liệu để trả lời",
        )

    def test_known_safety_question_is_answered(self):
        answer = ask_chatbot("quy định đội mũ bảo hộ")

        self.assertIn("Quy định Đội mũ bảo hộ", answer)

    def test_equipment_damage_keyword_still_matches(self):
        answer = ask_chatbot("thiết bị bảo hộ bị hỏng")

        self.assertIn("thiết bị bảo hộ bị nứt hỏng", answer)


if __name__ == "__main__":
    unittest.main()
