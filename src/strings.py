BOT_NAME = "Daily Tutor"

BOT_DESCRIPTION = "Daily Tutor provides daily practice with custom problems, tracks your progress, and delivers quick, personalized feedback. Type /subject to pick a subject!"

BOT_SHORT_DESCRIPTION = "Daily Tutor helps you practice daily, offering personalized problems, tracking progress, and giving instant feedback."

BOT_MENU_SUBJECT_DESCRIPTION = (
    "Set or review the subject you're currently focusing on. This helps me tailor questions just for you."
)

BOT_MENU_MEMO_DESCRIPTION = "Provide any additional memo you'd like me to consider when assisting you. Your notes help me understand what's important to you."

BOT_MENU_HINT_DESCRIPTION = (
    "Get a hint on how to solve the most recent question. This is helpful if you're stuck on an answer."
)

BOT_MENU_QUESTION_DESCRIPTION = (
    "Get a new question right away based on your current subject. Let's keep your learning on track!"
)

BOT_MENU_SOLVE_DESCRIPTION = (
    "Submit your solution to the latest question. I'll evaluate it and provide feedback to help you improve."
)

BOT_MENU_GIVE_UP_DESCRIPTION = "Give up and submit your solution to the latest question. I'll evaluate it and provide feedback to help you improve."

BOT_MENU_PLAY_DESCRIPTION = "Chat with me about anything regarding your subject! No question needed."

START_MESSAGE = (
    "Hey {user_first_name}! We're excited to have you here. To get started, please set your subject using /subject followed by the topic you're interested in. "
    "Once you've set your subject, I will prepare a question for you. You'll receive a new question tomorrow, but if you're eager to start, you can try a question right away using /question."
)

SUBJECT_SET_MESSAGE = 'Great choice! Your subject is now set to "{subject}". I will generate a tailored question for you by tomorrow, or if you\'re ready to dive in now, just type /question to get your first challenge!'

CURRENT_SUBJECT_MESSAGE = "Your current subject is: {subject}. I is working on a new question that you'll receive tomorrow. If you're eager to get started now, use /question to try a question immediately."

NO_SUBJECT_MESSAGE = (
    "It looks like you haven't set a subject yet. The subject helps me focus on what's most important to you. "
    "To set your subject, use /subject followed by your topic of interest. Once you've set it, you'll receive a new question tomorrow, or you can jump in right away by typing /question."
)

MEMO_UPDATED_MESSAGE = (
    "Your memo has been updated successfully! This memo will help me understand what's important to you. "
    "Feel free to update it anytime as your focus changes."
)

CURRENT_MEMO_MESSAGE = (
    "Here’s your current memo:\n> {memo}\n\n"
    "This memo is used by me to better assist you. If you need to change it, just use /memo followed by your updated information."
)

NO_MEMO_MESSAGE = (
    "You haven't set a memo yet. A memo helps me understand what's important to you right now. "
    "To set your memo, use /memo followed by your notes, and I will use this to better assist you."
)

PROMPT_SET_SUBJECT_MESSAGE = (
    "It seems you haven't told me your subject yet! The subject helps me tailor questions just for you. "
    "Please set your subject using /subject before we can generate a question."
)

GENERATING_QUESTION_MESSAGE = "Hang tight! I'm crafting a question just for you. This will only take a moment..."

QUESTION_GENERATION_FAILED_MESSAGE = "Oops, something went wrong while generating your question. Please try again later while our technicians look into the issue."

QUESTION_READY_MESSAGE = (
    "Here’s your {subject} question: {question}\n"
    "Take your time to think it through. Feel free to talk to me to get help if you need it.\n"
    "When you're ready, feel free to start solving it with /solve!"
)

NO_SESSION_MESSAGE = (
    "I couldn't find an active session. This doesn't happen often, but it means I can't find our conversation."
    "Please start a new session with /question and I'll get you a fresh challenge. Sorry about this!"
)

CHECKING_SOLUTION_MESSAGE = "Thanks! Let me submit your answer to the judge. We'll see how you did shortly!"

SUBMIT_SOLUTION_PROMPT_MESSAGE = "It seems you forgot to include your answer. Please submit it with /solve followed by your answer, so I can help you evaluate it."

NO_QUESTION_TO_SOLVE_MESSAGE = (
    "You don't have a question to solve yet! Please start a session with /question, and I'll give you a challenge."
)

TUTOR_ERROR_MESSAGE = "Oops, something went wrong on my end. I'm sorry about that! Please try again in a little bit, and I'll be here to help."

ADMIN_DELIVERED_DAILY_QUESTION = "🎉 Delivered the daily question!"
