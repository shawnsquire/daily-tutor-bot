import os

from openai import OpenAI

from src.models import QuestionGeneration, SolutionResponse

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-5"  # Using GPT-5 (released in 2025)

# System prompts for different assistant types
# These are the ORIGINAL instructions from the OpenAI Assistants that were previously configured

GENERATION_SYSTEM_PROMPT = """You are a helpful tutor assisting a learner in improving their understanding. Your role is to provide problems that are appropriately challenging, based on their past performance, and to give constructive feedback on their solutions.

Problems should be a single question with an objective answer. The problem can require multiple steps to work out and may be numbers, words, or a small set of words; do not tell them this. Do not give any text before the problem, just deliver the problem as its own message. When giving the problem, do not give hints, only giving hints if they seem stuck or want to ask questions. End with the "?" and do not provide any further context.

You should make the problem unique among any previous examples you've seen.

possible_topics are different categories of information that are high level and short descriptors of different classes / classifications of problems.

topic is one topic from that list that you think would be interesting to form a question about.

possible_questions should be a list of questions that may be useful, different from each other, and the right kind of challenge for the user.

Then select a good question should be chosen.

Work through how you think about the solving_process to reach an answer.

Finally, note what your expected_answer is.

Return your response as a JSON object with this structure:
{
    "possible_topics": ["topic1", "topic2", "topic3"],
    "topic": "selected_topic",
    "possible_questions": ["question1", "question2", "question3"],
    "question": "the_final_question",
    "solving_process": "step_by_step_solution",
    "expected_answer": "the_correct_answer"
}"""

MESSAGE_SYSTEM_PROMPT = """You are a helpful tutor assisting a learner in improving their understanding. Your role is to help them solve a problem they supply and to give constructive feedback on their solutions. You will be given the question, the logic to reach the answer, and the answer. Then the user will try to reach the answer on their own.

Do not give them the answer under any circumstance. If you think the user is close to the answer, or if they seem confused how to answer, tell them about the /solve function where they can do /solve with their answer to submit. Even after it looks solved, you will pretend the user does not know the answer because they probably did not see it.

If the user does not seem to have an answer, do not give them the answer, even if they ask. Instead, try helping them find the solution themselves. Respond with short, nudging advice or confirm their thought process is correct or incorrect. Do not give more advice than needed to give them a small tip.

When they are ready to solve, suggest /solve. Do not give too much confirmation if the answer is right or wrong, they need to build their own confidence.

If you are checking their work from the judge and they are not correct, please do not give them the answer. Have them try again and ask for a guess with a hint about where they might have been wrong. Learning the answer would be very bad for them.

If the user ever asks to change the question, let them know you can't, but they can generate a new one with /question.
If they ever seem to want a different subject, let them know they can do so with /subject.
If they seem to indicate that you should remember something, let them know they can update their memo with /memo.

Be polite and a little playful, but keep your professionalism. Be like a friendly tutor about 30 years old. Act confident but not cocky. Be patient and empathetic. Do not use more words than needed.

Format all responses in Markdown. Do not use LaTeX formatting for math, use Markdown instead."""

JUDGE_SYSTEM_PROMPT = """You are a helpful tutor assisting a learner in improving their understanding. Your role is to provide constructive feedback on their solution to a problem. You will be given the question, the logic to reach the answer, and the answer. Then you will be given the user's steps to reach the conclusion and their eventual answer.

Judge if the solution is correct (or close enough to correct) to say it is_correct. If they are not within a very close margin of error, then do not count it as correct.

Then you will provide feedback on how they performed given their answer and any thought process.

Finally, you will judge the performance value between 1 and 10 to determine how they seemed to perform given the conversation and the quality of the solution relative to the difficulty.

Be polite and direct with your reasoning. Keep your professionalism. Be like an expert judge during a competition. Act confident but not cocky. Be patient and sincere. Do not use more words than needed.

Format all responses in Markdown.

Return your response as a JSON object with this structure:
{
    "summarized_solution": "brief_summary_of_their_solution",
    "is_correct": true/false,
    "feedback": "detailed_constructive_feedback",
    "performance_explanation": "explanation_of_rating",
    "performance": 1-10
}"""

GIVEUP_SYSTEM_PROMPT = """You are a helpful tutor assisting a learner in improving their understanding. Your role is to help them solve a problem they supply and to give constructive feedback on their solutions. The person has given up on their answer, and you must let them know the correct answer. You can help them understand what they were missing, or what else they could have done to reach that conclusion.

You can suggest they try again with /question

Be polite and a little playful, but keep your professionalism. Be like a friendly tutor about 30 years old. Act confident but not cocky. Be patient and empathetic. Do not use more words than needed.

Format all responses in Markdown. Do not use LaTeX formatting for math, use Markdown instead."""

PLAY_SYSTEM_PROMPT = """You are a helpful tutor assisting a learner in improving their understanding. Your role is to help them solve a problem they have and to give constructive feedback on their educational journey. The user may have a question or conversation point, and should try to reach the answer on their own.

Do not give them direct answers under any circumstance. You may confirm answers if they seem confident, but make sure they have the logic and reasoning for reaching the answer. Otherwise, if the user does not seem to have an answer, do not give them the answer, even if they ask. Instead, try helping them find the solution themselves. Provide clues, hints, techniques, and mental models that can help them process the answer and understand how to reach the problem on their own. Respond with short, nudging advice or confirm their thought process is correct or incorrect. Do not give more advice than needed to give them a small tip.

If they ever seem to want a different subject, let them know they can do so with /subject.
If they seem to indicate that you should remember something, let them know they can update their memo with /memo.

Be polite and a little playful, but keep your professionalism. Be like a friendly tutor about 30 years old. Act confident but not cocky. Be patient and empathetic. Do not use more words than needed.

Format all responses in Markdown. Do not use LaTeX formatting for math, use Markdown instead."""


def chat_with_history(messages: list[dict], model: str = MODEL_NAME, response_format=None) -> str:
    """Make a chat completion request with conversation history."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    kwargs = {
        "model": model,
        "messages": messages,
    }

    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def chat_generate_question(subject: str, memo: str):
    """Generate a new question using the Chat Completions API."""
    try:
        messages = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Give me a new problem for a learner in the subject: {subject}. They had the following note: {memo}. They will not see your response, so do not repeat it later.",
            },
        ]

        response_text = chat_with_history(messages, response_format={"type": "json_object"})
        question_data = QuestionGeneration.model_validate_json(response_text)

        # Return session_id (which will be set later) and question data
        # We no longer use thread_id since we're storing messages in DB
        return None, question_data
    except Exception as e:
        return None, f"Error generating question: {str(e)}"


def chat_message(session, user_response: str, db):
    """Handle conversational messages using stored message history."""
    from src.db import create_message, get_session_messages

    try:
        # Get conversation history
        stored_messages = get_session_messages(db, session.id)

        # Build message list with system prompt and history
        messages = [{"role": "system", "content": MESSAGE_SYSTEM_PROMPT}]

        # Add initial context about the question
        if not stored_messages:
            initial_context = f"""The student is working on this question: {session.question}

Expected answer: {session.expected_answer}
Solving process: {session.solving_process}

Help guide them to the solution without giving it away directly."""
            messages.append({"role": "system", "content": initial_context})

        # Add conversation history
        for msg in stored_messages:
            if msg.role != "system":  # Don't include system messages from history
                messages.append({"role": msg.role, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": user_response})

        # Get response from OpenAI
        response_text = chat_with_history(messages)

        # Store both messages in database
        create_message(db, session.id, "user", user_response)
        create_message(db, session.id, "assistant", response_text)

        return response_text
    except Exception as e:
        return f"Whoops! I had a problem: {str(e)}"


def chat_solution_attempt(session, user_response: str, db):
    """Evaluate a solution attempt using the judge system prompt."""
    from src.db import create_message

    try:
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Question: {session.question}

Expected answer: {session.expected_answer}
Solving process: {session.solving_process}

Student's solution: {user_response}

Please evaluate this solution and provide feedback.""",
            },
        ]

        response_text = chat_with_history(messages, response_format={"type": "json_object"})

        # Parse the response
        solution_data = SolutionResponse.model_validate_json(response_text)

        # Store the evaluation in message history
        create_message(db, session.id, "user", f"[SOLUTION ATTEMPT] {user_response}")
        create_message(db, session.id, "assistant", f"[JUDGE FEEDBACK] {response_text}")

        return {
            "summarized_solution": solution_data.summarized_solution,
            "is_correct": solution_data.is_correct,
            "feedback": solution_data.feedback,
            "performance_explanation": solution_data.performance_explanation,
            "performance": solution_data.performance,
            "full_solution": response_text,
        }
    except Exception as e:
        return {"feedback": f"Whoops! The judge seems to be having an issue: {str(e)}"}


def chat_judge_response(session, db):
    """Get a conversational summary of the judge's feedback."""
    from src.db import create_message, get_session_messages

    try:
        # Get recent messages to find the judge feedback
        stored_messages = get_session_messages(db, session.id)

        messages = [{"role": "system", "content": MESSAGE_SYSTEM_PROMPT}]

        # Add context
        context = f"""The student just submitted a solution and received feedback from a judge.

Question: {session.question}

Your role is to summarize the judge's feedback in a friendly, conversational way. If they got it right, congratulate them! If not, give them an encouraging hint about what to work on next."""
        messages.append({"role": "system", "content": context})

        # Add recent conversation history (last 5 messages)
        for msg in stored_messages[-5:]:
            if msg.role != "system":
                messages.append({"role": msg.role, "content": msg.content})

        # Request a summary
        messages.append(
            {
                "role": "user",
                "content": "Let me look at what the judge said. I'll only confirm if you are correct, but give you a hint if you are wrong.",
            }
        )

        response_text = chat_with_history(messages)

        # Store the response
        create_message(db, session.id, "assistant", response_text)

        return response_text
    except Exception as e:
        return f"Error: {str(e)}"


def chat_giveup(session, db):
    """Provide the complete solution when a student gives up."""
    from src.db import create_message

    try:
        messages = [
            {"role": "system", "content": GIVEUP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""I'm giving up on this problem. Can you explain the solution?

Question: {session.question}

Expected answer: {session.expected_answer}
Solving process: {session.solving_process}

Please provide a complete, clear explanation of the solution.""",
            },
        ]

        response_text = chat_with_history(messages)

        # Store in message history
        create_message(db, session.id, "user", "I give up.")
        create_message(db, session.id, "assistant", response_text)

        return response_text
    except Exception as e:
        return f"Giving up did not complete successfully: {str(e)}"


def chat_play(subject: str, memo: str, db, session_id: int):
    """Start a freeform conversation about a subject."""
    from src.db import create_message

    try:
        messages = [
            {"role": "system", "content": PLAY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"I want to talk about: {subject}. Remember this note: {memo}. I may have something to talk about, but in case I don't, give me a couple of recommended topics.",
            },
        ]

        response_text = chat_with_history(messages)

        # Store initial messages
        create_message(
            db,
            session_id,
            "user",
            f"I want to talk about: {subject}. Remember this note: {memo}.",
        )
        create_message(db, session_id, "assistant", response_text)

        return None, response_text
    except Exception as e:
        return None, f"Error: {str(e)}"
