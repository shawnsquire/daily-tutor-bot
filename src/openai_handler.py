import os
from openai import OpenAI
from src.models import *

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Assistant IDs
GENERATION_ASSISTANT = "asst_Vw21sPPzzZuqkRM42n6X27OZ"
MESSAGE_ASSISTANT = "asst_3QnAUu8jMl9j0n8VFyWuyv9G"
JUDGE_ASSISTANT = "asst_icrfgkOoEozOuCRSO33tvWlk"
GIVEUP_ASSISTANT = "asst_h8EDYFMqiaJqIAw4WfFlwChS"

def chat_generate_question(subject, memo):
    # Create the OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Get the assistant
    assistant = client.beta.assistants.retrieve(GENERATION_ASSISTANT)

    # Create a thread with the user's message
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": f'Give me a new problem for a learner in the subject: {subject}. They had the following note: {memo}. They will not see your response, so do not repeat it later.'
            }
        ]
    )


    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        msg_text = messages.data[0].content[0].text.value
        question_data = QuestionGeneration.model_validate_json(msg_text)
        return thread.id, question_data
    else:
        return 0, run.status

def chat_message(session, user_response):
    # Create the OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Retrieve the assistant for answering solutions
    assistant = client.beta.assistants.retrieve(MESSAGE_ASSISTANT)

    # Get the thread_id
    thread_id = session.thread_id

    # Add the user response
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_response
    )

    # Run and wait for the AI agent
    run = client.beta.threads.runs.create_and_poll(
        assistant_id=assistant.id,
        thread_id=thread_id
    )


    # Check if the run completed successfully
    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=run.thread_id)
        msg_text = messages.data[0].content[0].text.value

        return msg_text


    return {"feedback": f"Whoops! I had a problem. {run.last_error.message} ({run.last_error.code})"}



def chat_solution_attempt(session, user_response):
    # Create the OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Retrieve the assistant for answering solutions
    assistant = client.beta.assistants.retrieve(JUDGE_ASSISTANT)

    # We need there to be a thread ID on this
    if not session.thread_id:
        return

    # Get the thread_id
    thread_id = session.thread_id

    # TODO: Check about this being user versus assistant
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_response
    )

    run = client.beta.threads.runs.create_and_poll(
        assistant_id=assistant.id,
        thread_id=thread_id
    )

    # Check if the run completed successfully
    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=run.thread_id)
        msg_text = messages.data[0].content[0].text.value

        # Parse the response using Pydantic
        solution_data = SolutionResponse.model_validate_json(msg_text)

        # Return all the necessary information, including thread_id if it was newly created
        return {
            "summarized_solution": solution_data.summarized_solution,
            "is_correct": solution_data.is_correct,
            "feedback": solution_data.feedback,
            "performance_explanation": solution_data.performance_explanation,
            "performance": solution_data.performance,
            "full_solution": msg_text
        }
    else:
        return {"feedback": f"Whoops! The judge seems to be having an issue. {run.last_error.message} ({run.last_error.code})"}

def chat_judge_response(session):
    # Create the OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Retrieve the assistant for answering solutions
    assistant = client.beta.assistants.retrieve(MESSAGE_ASSISTANT)

    # Get the thread_id
    thread_id = session.thread_id or None

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="assistant",
        content="Let me look at what the judge said. I'll only confirm if you are correct, but give you a hint if you are wrong."
    )

    run = client.beta.threads.runs.create_and_poll(
        assistant_id=assistant.id,
        thread_id=thread_id
    )

    # Check if the run completed successfully
    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=run.thread_id)
        msg_text = messages.data[0].content[0].text.value

        return msg_text


    return {"feedback": f"Error: {run.last_error.message} ({run.last_error.code})"}

def chat_giveup(session):
    # Create the OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Retrieve the assistant for answering solutions
    assistant = client.beta.assistants.retrieve(GIVEUP_ASSISTANT)

    # Get the thread_id
    thread_id = session.thread_id or None

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content="I give up."
    )

    run = client.beta.threads.runs.create_and_poll(
        assistant_id=assistant.id,
        thread_id=thread_id
    )

    # Check if the run completed successfully
    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=run.thread_id)
        msg_text = messages.data[0].content[0].text.value

        return msg_text

    return f"Giving up did not complete successfully: {run.status}"
