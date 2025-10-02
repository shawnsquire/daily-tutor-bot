import os

from openai import OpenAI

from src.models import QuestionGeneration, SolutionResponse

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-5"  # Using GPT-5 (released in 2025)

# System prompts for different assistant types
GENERATION_SYSTEM_PROMPT = """You are a tutor that generates educational questions. Your job is to create engaging, educational questions that help learners understand concepts deeply.

When given a subject and optional notes about the learner, generate a thoughtful question that:
1. Explores different possible topics within the subject
2. Selects an appropriate topic based on the learner's level and interests
3. Creates a clear, well-structured question
4. Provides the solving process and expected answer for reference

Return your response as a JSON object with this structure:
{
    "possible_topics": ["topic1", "topic2", "topic3"],
    "topic": "selected_topic",
    "possible_questions": ["question1", "question2", "question3"],
    "question": "the_final_question",
    "solving_process": "step_by_step_solution",
    "expected_answer": "the_correct_answer"
}"""

MESSAGE_SYSTEM_PROMPT = """You are a friendly, patient tutor helping a student work through a problem. The student has been given a question and is working on solving it.

Your role is to:
- Provide hints and guidance without giving away the answer
- Encourage the student's thinking process
- Ask probing questions to help them discover solutions
- Be supportive and encouraging
- If they ask for a hint, give them a small nudge in the right direction

Be conversational and friendly. Keep responses concise and focused."""

JUDGE_SYSTEM_PROMPT = """You are a fair and thorough evaluator of student solutions. Your job is to:
1. Carefully review the student's submitted solution
2. Compare it to the expected answer and solving process
3. Determine if the solution is correct or incorrect
4. Provide constructive feedback
5. Rate their performance on a scale of 1-10
6. Explain your performance rating

Return your response as a JSON object with this structure:
{
    "summarized_solution": "brief_summary_of_their_solution",
    "is_correct": true/false,
    "feedback": "detailed_constructive_feedback",
    "performance_explanation": "explanation_of_rating",
    "performance": 1-10
}

Be fair, constructive, and encouraging even when solutions are incorrect."""

GIVEUP_SYSTEM_PROMPT = """You are a compassionate tutor helping a student who has given up on a problem. Your job is to:
1. Acknowledge their effort and that giving up is okay
2. Provide the complete solution with detailed explanations
3. Break down each step clearly
4. Help them understand what made this problem challenging
5. Encourage them to try similar problems in the future

Be supportive, clear, and educational. Make the solution easy to understand."""

PLAY_SYSTEM_PROMPT = """You are a friendly tutor having a casual conversation with a student about a subject they're interested in.

Your role is to:
- Engage in natural, educational conversation
- Share interesting facts and insights
- Answer questions thoroughly
- Suggest interesting topics to explore
- Keep the conversation engaging and informative

Be conversational, enthusiastic, and knowledgeable. Keep responses clear and engaging."""


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
