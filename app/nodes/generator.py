from app.services.llm import llm
from app.models.schemas import GeneratedQuestion
from app.graph.state import ExamState
from app.services.vector_store import retrieve_jlpt_content 

def generator_node(state: ExamState):
    """
    Generates questions based on Major Type (Section) and Minor Type (Sub-Type).
    Uses the hierarchy to determine data retrieval and prompting logic.
    """
    if not state.get("current_task"):
        return {"generated_questions": None}
    
    current_count = state.get("retry_count", 0)
    mode = state.get("generation_mode", "standard")
    
    # --- 1. EXTRACT TYPES ---
    task = state["current_task"]
    section = task.get("section")       # Major Type: "Vocabulary", "Grammar", etc.
    sub_type = task.get("sub_type")     # Minor Type: "Kanji reading", "Orthography", etc.
    level = state['jlpt_level']
    count = task.get("count", 1)
    
    print(f"--- Generating [{section} / {sub_type}] x {count} (Attempt {current_count + 1}) ---")
    
    # --- 2. DETERMINE DATA RETRIEVAL (Based on Section) ---
    db_type = None
    
    if section in ["Reading", "Listening"]:
        # Reading and Listening generate content from scratch, no specific DB point needed
        db_type = None
    elif section == "Grammar":
        db_type = "grammar"
    elif section == "Vocabulary":
        # Vocabulary DB doesn't have level property, so we skip it to avoid unsuitable words.
        # LLM will generate suitable words from scratch for non-kanji vocabulary.
        if "kanji" in sub_type.lower():
            db_type = "kanji"
        else:
            db_type = None
    
    # --- 3. FETCH DATA (If needed) ---
    data_list = None
    
    if db_type:
        if mode == "reroll":
            print(f"--- Reroll: Fetching new {db_type} data ---")
            try:
                data_list = retrieve_jlpt_content(level, db_type, count)
            except ValueError as e:
                print(f"Reroll failed: {e}")
                data_list = state.get("current_data_payload")
        else:
            data_list = state.get("current_data_payload")
            if data_list:
                data_list = data_list[:count]
            if not data_list:
                try:
                    data_list = retrieve_jlpt_content(level, db_type, count)
                except Exception as e:
                    print(f"Failed to fetch {db_type} data: {e}")
                    pass
        
        # We no longer fail if data_list is None. 
        # The LLM will fall back to generating targets on its own.
        # if not data_list:
        #     return {"generated_questions": None, "retry_count": current_count + 1}

    # --- 4. GENERATE PROMPTS (Based on Sub-Type) ---
    
    # Format target words for prompt
    targets_info = ""
    if data_list:
        for idx, d in enumerate(data_list):
            item_name = d.get('kanji') or d.get('word', "Unknown")
            targets_info += f"Target {idx+1}:\n- Word/Kanji: {item_name}\n"
            if 'vocabulary_compounds' in d: targets_info += f"- Reading: {d.get('vocabulary_compounds')}\n"
            if 'reading' in d: targets_info += f"- Reading: {d.get('reading')}\n"
            if 'meaning' in d: targets_info += f"- Meaning: {d.get('meaning')}\n"
            if 'grammer_structure' in d: targets_info += f"- Structure: {d.get('grammer_structure')}\n"
            targets_info += "\n"
    elif db_type:
        targets_info += f"No specific targets retrieved from DB. You MUST conceptually invent {count} appropriate {db_type} target items suitable for JLPT {level} and use them as your targets.\n\n"
    
    # --- VOCABULARY PROMPTS ---
    if section == "Vocabulary":
        
        if sub_type == "Kanji reading":
            base_instructions = f"""
            ## TASK: Create {count} Kanji Reading Questions (JLPT {level} style)

            ### TARGETS:
            {targets_info}

            ### INSTRUCTIONS:
            1. Write a natural Japanese sentence (15-30 characters) containing the target kanji word.
            2. Underline the kanji word in the sentence using 【 】brackets.
            3. The question asks: "下線部の読み方として最も適当なものを、次のA～Dの中から一つ選びなさい。"

            ### OPTION RULES:
            - Option A-D: Four different hiragana readings
            - CORRECT: The actual reading of the underlined kanji
            - DISTRACTORS: Must be plausible but incorrect readings
            - Use similar-looking kanji readings
            - Use common misreadings at this level
            - All options must be valid Japanese readings

            ### EXAMPLE FORMAT:
            問題: 田中さんは【有名】な作家です。
            A. ゆうめい (correct)
            B. ゆうめ
            C. ゆめい
            D. ゆめ
            """
            
        elif sub_type == "Orthography":
            # Reverse logic: Kana -> Kanji
            base_instructions = f"""
            ## TASK: Create {count} Orthography Questions (Kanji Selection) - JLPT {level} style

            ### INSTRUCTIONS:
            1. Select {count} suitable {level} vocabulary words that have kanji.
            2. Write a context sentence where the target word is written in hiragana (underlined with 【 】).
            3. The question asks students to select the correct kanji writing for the underlined word.
            4. Question text: "下線部の漢字として最も適当なものを、次のA～Dの中から一つ選びなさい。"

            ### OPTION RULES:
            - All 4 options must be KANJI writings
            - CORRECT: The actual correct kanji for your chosen word
            - DISTRACTORS: Must be incorrect kanji that could be confused
            - Same reading, different kanji (homophones)
            - Similar-looking kanji
            - Plausible but contextually wrong kanji
            - At least 1-2 should share the same reading

            ### EXAMPLE:
            問題: 毎日、日本語を【べんきょう】しています。
            A. 勉強 (correct)
            B. 勉強
            C. 勉教
            D. 弁強
            """
            
        elif sub_type == "Word formation":
            base_instructions = f"""
            ## TASK: Create {count} Word Formation Questions (Derivations) - JLPT {level} style

            ### INSTRUCTIONS:
            1. Select {count} suitable {level} base words for word formation.
            2. Write a natural Japanese sentence with ONE blank (　　).
            3. Provide the BASE WORD in brackets after the sentence.
            4. The student must choose the correctly derived form.

            ### RULES FOR {level} LEVEL:
            - N5-N4: Basic verb/noun forms (e.g., 食べる → 食べた)
            - N3-N2: Compound words, suffix derivatives (e.g., 便利 → 便利さ)
            - N1: Complex derivations, idiomatic compounds

            ### OPTION RULES:
            - All 4 options must be different word forms derived from the base word
            - CORRECT: The form that fits grammatically in the sentence
            - DISTRACTORS: Other derived forms that are:
            - Grammatically incorrect in this context
            - Different parts of speech
            - Common errors made by learners

            ### EXAMPLE:
            問題: この本はとても（　　）です。　［面白い］
            A. 面白かった
            B. 面白くない
            C. 面白さ (correct)
            D. 面白く
            """
            
        elif sub_type =="Contextually-defined expressions":
            base_instructions = f"""
            ## TASK: Create {count} Context-Rich Vocabulary Questions - JLPT {level} style

            ### INSTRUCTIONS:
            1. Select {count} suitable {level} vocabulary words as the targets.
            2. Write a context sentence for the word.
            3. Include a blank (　　) where the target word should go.
            4. The context must clearly indicate the meaning without being too obvious.
            5. Sentence should be natural and appropriate for {level} level.

            ### OPTION RULES:
            - All 4 options must be {level}-appropriate vocabulary words
            - CORRECT: The chosen target word
            - DISTRACTORS: Must be:
            - Same part of speech
            - Similar in meaning or usage
            - Plausible in the sentence but contextually wrong
            - NOT obviously incorrect

            ### DIFFICULTY GUIDELINES:
            - N5-N4: Common daily vocabulary
            - N3: Semi-abstract words, compound words
            - N2: Abstract words, formal vocabulary
            - N1: Rare words, specialized vocabulary, idioms
            """
        elif sub_type =="Paraphrases":
            base_instructions = f"""
            ## TASK: Create {count} Paraphrase Questions - JLPT {level} style

            ### INSTRUCTIONS:
            1. Select {count} target vocabulary words appropriate for JLPT {level}.
            2. Write a sentence containing the target word.
            3. Underline the target word with 【 】.
            4. Question asks: "下線部と同じ意味で置き換えられる言葉を、次のA～Dの中から一つ選びなさい。"

            ### OPTION RULES:
            - CORRECT: A word/phrase that can directly replace the underlined word
            - DISTRACTORS: Words that:
            - Are related but not synonymous
            - Have similar connotations but different meanings
            - Are commonly confused with the correct answer

            ### EXAMPLE:
            問題: 彼は【真面目に】仕事をしている。
            A. まじめに (correct - same meaning in different form)
            B. きびしく
            C. ていねいに
            D. ゆっくりと
            """
        elif sub_type =="Usage":
            base_instructions = f"""
            ## TASK: Create {count} Usage Questions - JLPT {level} style

            ### INSTRUCTIONS:
            1. Select {count} target vocabulary words appropriate for JLPT {level}.
            2. For EACH word, create 4 different sentences using the chosen word.
            3. One sentence uses the word CORRECTLY (natural, proper context).
            4. Three sentences use the word INCORRECTLY (wrong collocation, wrong context, or unnatural).
            5. Question: "次の文の中で、（Chosen Word）が正しく使われている文を一つ選びなさい。"

            ### OPTION RULES:
            - Each option MUST be a COMPLETE, grammatically valid sentence structure.
            - CORRECT: Sentence where the word is used naturally.
            - DISTRACTORS: Sentences where:
              - The word doesn't collocate naturally
              - The meaning doesn't fit the context
              - A different word should be used instead
            - CRITICAL: DO NOT use grammatically broken or incomplete sentences as distractors (e.g. "売上が比較です" is invalid). The sentence structure itself must be complete.

            ### COMMON ERRORS TO TEST:
            - Wrong particle usage
            - Wrong verb conjugation
            - Collocation mismatches
            - Contextual inappropriateness
            """
    # --- GRAMMAR PROMPTS ---
    elif section == "Grammar":
        
        if sub_type == "Sentential grammar 1 (Selecting grammar form)":
            base_instructions = f"""
            ## TASK: Create {count} Grammar Selection Questions - JLPT {level} style

            ### TARGETS:
            {targets_info}

            ### INSTRUCTIONS:
            1. For EACH target grammar point, write a sentence with ONE blank (　　) requiring the target grammar.
            2. Provide appropriate context (situation, time, speaker's attitude).
            3. Context must clearly indicate which grammar pattern is needed.

            ### OPTION RULES:
            - All 4 options must be grammar forms (particles, verb forms, set phrases)
            - CORRECT: The exact target grammar point appropriate for the sentence
            - DISTRACTORS: Must be:
            - Similar grammar patterns at {level} level
            - Commonly confused forms
            - Grammatically possible but contextually wrong
            - NOT nonsense words

            ### GRAMMAR POINTS BY LEVEL:
            - N5: Basic particles (は, が, を, に, で), simple verb forms
            - N4: て-forms, potential form, basic conditionals
            - N3: Causative, passive, intermediate conditionals, formal expressions
            - N2: Advanced conditionals, formal spoken patterns, compound particles
            - N1: Literary forms, advanced formal patterns, nuanced expressions

            ### EXAMPLE:
            問題: 明日の会議には、社長（　　）出席する予定です。
            A. にも
            B. にも (correct - "even the president")
            C. だけ
            D. しか
            """
            
        elif sub_type == "Sentential grammar 2 (Sentence composition)":
            base_instructions = f"""
            ## TASK: Create {count} Sentence Composition Questions (Scrambled Sentences) - JLPT {level} style

            ### INSTRUCTIONS:
            1. Think of a single natural Japanese sentence appropriate for {level} level.
            2. Break a continuous syntactic part of the sentence into 4 scrambleable structural chunks.
            3. The question format MUST show exactly 4 blanks in this exact format: ＿＿　＿＿　★　＿＿
            4. The student must conceptually unscramble the 4 chunks to complete the sentence syntax, and the answer is the chunk that falls on the star (★).
            5. CRITICAL: Do NOT list chronological events or steps (e.g. "leave room -> walk down hall -> look out window"). Scramble grammar syntax, not time events!

            ### OPTION RULES:
            - The 4 options (A, B, C, D) are the 4 grammatical chunks to be unscrambled.
            - DO NOT provide orderings like "1-2-3-4" as options.
            - CORRECT: The specific chunk representing the 3rd position (★).

            ### EXAMPLE:
            問題: あの人は ＿＿　＿＿　★　＿＿　いる。
            A. 知って
            B. 何でも
            C. かのように (correct)
            D. 話して

            Explanation: The correct syntax order is 何でも(B) -> 知って(A) -> かのように(C) -> 話して(D) -> いる。 The star is the 3rd spot, aligning with 'かのように' (C).
            """
            
        elif sub_type == "Text grammar":
            base_instructions = f"""
            ## TASK: Create {count} Text Grammar Questions (Cloze-style) - JLPT {level} style

            ### TARGETS:
            {targets_info}

            ### INSTRUCTIONS:
            1. Write a SHORT PASSAGE (3-5 sentences, 100-200 characters) for EVERY target grammar point. (Or one larger passage containing {count} blanks).
            2. Include blanks (　　) within the passage corresponding to the targets.
            3. The passage should have:
               - Clear context and logical flow
               - Natural paragraph structure
               - Grammar that requires understanding context

            ### PASSAGE GUIDELINES:
            - Topic: Daily life, work, school, or social situations
            - Style: Appropriate for {level} (polite form for N5-N3, mix for N2-N1)
            - Context must indicate which grammar is needed

            ### OPTION RULES:
            - All options are grammar forms or connecting phrases
            - CORRECT: Grammar that fits the context and meaning
            - DISTRACTORS: Grammar that:
              - Has similar meaning but wrong nuance
              - Fits grammatically but not contextually
              - Is commonly confused with the correct answer

            ### EXAMPLE:
            問題:
            明日は試験だ。一晩で全部覚えるのは無理だ（　　）、重要なところだけ復習しよう。
            A. から
            B. ので
            C. けれど (correct)
            D. ため
            """

    # --- READING PROMPTS ---
    elif section == "Reading":
        if sub_type == "Information retrieval":
            length = "Info"
        else:
            length = "Short" if "short" in sub_type.lower() else "Medium" if "mid" in sub_type.lower() else "Long"
            
        if length == "Info":
            base_instructions = f"""
            ## TASK: Create {count} Information Retrieval Reading Questions - JLPT {level} style

            ### PASSAGE REQUIREMENTS:
            - Format: Real-world practical documents like event schedules, notices, or advertisements.
            - Must include itemized lists, pricing, times, or bullet points.
            
            ### QUESTION REQUIREMENTS:
            - Ask to find specific info based on conditions (e.g., "A student wants to visit on Sunday. How much?").
            
            ### OPTION RULES:
            - CORRECT: Matches all conditions in the prompt exactly.
            - DISTRACTORS: Plausible but fails one condition (e.g., wrong day's price).
            """
        elif length == "Short":
            base_instructions = f"""
            ## TASK: Create {count} Short Reading Comprehension Questions - JLPT {level} style

            ### PASSAGE REQUIREMENTS:
            - Length: 80-150 characters (N5-N4), 100-200 characters (N3-N2), 150-250 characters (N1)
            - Topic: Daily life, notices, short messages, simple explanations
            - Style: Clear, direct Japanese appropriate for {level}

            ### PASSAGE TYPES (choose appropriately):
            - Notices/Announcements
            - Personal messages/emails
            - Simple instructions
            - Short descriptions

            ### QUESTION REQUIREMENTS:
            - One question testing comprehension
            - Question types:
              - Main idea: "この文章からわかることは何ですか。"
              - Detail: "Aさんは何時に来ますか。"
              - Purpose: "このお知らせの目的は何ですか。"

            ### OPTION RULES:
            - All 4 options must be plausible
            - CORRECT: Information stated or clearly implied in the passage
            - DISTRACTORS:
              - Information NOT in the passage
              - Contradicts the passage
              - Too general or too specific
              - Common misinterpretations
            """
        elif length == "Medium":
            base_instructions = f"""
            ## TASK: Create {count} Medium-Length Reading Comprehension Questions - JLPT {level} style

            ### PASSAGE REQUIREMENTS:
            - Length: 200-400 characters (N3), 300-500 characters (N2-N1)
            - Topic: Opinion essays, explanations, workplace scenarios
            - Structure: Introduction → Body → Conclusion
            - Style: Mix of formal and semi-formal Japanese

            ### PASSAGE TYPES:
            - Opinion pieces
            - Explanatory texts
            - Problem-solution format
            - Comparisons

            ### QUESTION REQUIREMENTS:
            - 1 question testing deeper comprehension
            - Question types:
              - Author's opinion: "筆者が最も言いたいことは何ですか。"
              - Cause-effect: "なぜ～と書いているか。"
              - Implication: "～とはどういう意味か。"

            ### OPTION RULES:
            - CORRECT: Accurately reflects the passage
            - DISTRACTORS:
              - Partial truths
              - Misleading interpretations
              - Information from wrong part of passage
              - Opposite of author's intention
            """
        elif length == "Long":
            base_instructions = f"""
            ## TASK: Create {count} Long Reading Comprehension Questions - JLPT {level} style

            ### PASSAGE REQUIREMENTS:
            - Length: 500-800 characters
            - Topic: Complex arguments, academic topics, social issues
            - Structure: Multi-paragraph with logical development
            - Style: Formal written Japanese (書き言葉)

            ### PASSAGE TYPES:
            - Critical essays
            - Academic explanations
            - Social commentary

            ### QUESTION REQUIREMENTS:
            - Test understanding of logical structure
            - Question types:
              - Logical conclusion
              - Author's reasoning
              - Paragraph relationships

            ### OPTION RULES:
            - CORRECT: Requires synthesis of multiple parts of the passage
            - DISTRACTORS:
              - Superficial interpretations
              - Information from only one paragraph
              - Misunderstanding of logical structure
            """

    # --- LISTENING PROMPTS ---
    elif section == "Listening":
        if sub_type == "Quick response":
            base_instructions = f"""
            ## TASK: Create {count} Quick Response (即時応答) Listening Questions - JLPT {level} style
            
            ### SCRIPT REQUIREMENTS:
            - Very short single utterance (1 sentence, 3-10 seconds).
            - NO Dialogue. Just one statement.
            
            ### FORMAT AND OPTIONS:
            - Provide the single utterance.
            - Provide exactly 3 or 4 short response options (A, B, C, D).
            - CORRECT: Natural response to the utterance.
            - DISTRACTORS: Unnatural responses, or answering a different question.
            """
        else:
            base_instructions = f"""
            ## TASK: Create {count} Listening Comprehension Questions - JLPT {level} style

            ### TASK TYPE: {sub_type}

            ### SCRIPT REQUIREMENTS:
            - Natural Japanese conversation or monologue
            - Length: 30-60 seconds when read aloud
            - Style: Appropriate for the situation (polite/casual)
            - Include relevant background sounds in [brackets] if needed

            ### SCRIPT TYPES BY sub_type:
            - "Task-based comprehension": Instructions followed by action → What does the person do?
            - "Point comprehension": Conversation focusing on specific points → What is the specific detail (reason, feeling, etc.)?
            - "Summary comprehension": Monologue or conversation → What is the main point or overall theme?
            - "Utterance expressions": Short phrase paired with a picture or context → What is the appropriate expression for the situation?
            - "Integrated comprehension": Longer, complex listening involving multiple texts or speakers → Compare and synthesize information.

            ### QUESTION FORMAT:
            1. Provide the SCRIPT (conversation/monologue)
            2. Question about the script content
            3. Mark correct answer clearly

            ### OPTION RULES:
            - All 4 options must be plausible answers
            - CORRECT: Matches the script content
            - DISTRACTORS:
              - Information mentioned but not the answer
              - Common misconceptions
              - Similar-sounding words/phrases

            ### EXAMPLE:
            Script:
            男：明日の会議、何時に始まりますか。
            女：もともとは10時だったんですが、社長が遅れるそうなので、30分遅らせることになりました。
            男：あ、そうですか。ありがとうございます。

            Question: 会議は何時に始まりますか。
            A. 9時30分
            B. 10時
            C. 10時30分 (correct)
            D. 11時
            """

    else:
        base_instructions = "Create a standard JLPT question."

    # --- 5. ASSEMBLE FINAL PROMPT ---
    
    if current_count > 0:
        feedback = state.get("validation_feedback", "")
        final_instructions = f"""
        {base_instructions}
        
        RETRY INSTRUCTIONS:
        Previous attempt rejected for some questions: {feedback}
        Fix the issue while maintaining the strict rules for {sub_type}. Generate {count} correct questions.
        """
    else:
        final_instructions = base_instructions

    system_prompt = f"""
    You are a strict JLPT examiner for {level}.
    
    {final_instructions}
    
    Ensure output matches the provided schema perfectly and contains exactly {count} independent questions.
    
    CRITICAL SCHEMA MAPPING RULES:
    - Vocabulary & Grammar: "passage_text" MUST be null. "question_text" MUST combine BOTH the instructional text (e.g., "下線部の漢字として最も適当なものを...") AND the target sentence.
    - Reading: "passage_text" MUST contain the reading passage. "question_text" MUST contain the specific question about the passage.
    - Listening: "passage_text" MUST be null. "dialogue_script" MUST contain the conversation/monologue script. "question_text" MUST contain the specific question.
    - YOU MUST include the `correct_answer_label` field with the letter of the correct option (e.g., "A", "B", "C", or "D").
    - YOU MUST include `explanation_en` and `explanation_jp` for every question to explain why the answer is correct and why the distractors are wrong.
    
    CRITICAL QUALITY CONTROLS (TO PASS VALIDATION):
    1. STRICT UNIQUENESS: Ensure ONLY ONE option is undeniably correct. Distractors MUST NOT be grammatically or contextually acceptable answers (e.g., do not test 'から' vs 'ので' if both fit the context).
    2. STRICT DIFFICULTY LIMITS: The target vocabulary, grammar, and kanji MUST strictly match the {level} curriculum. Do NOT use N5/N4 items on an N3 test (too easy), and do NOT use N2/N1 items on an N3 test (too hard).
    3. REAL-WORD DISTRACTORS: All distractors MUST be real Japanese words or plausible, common learner mistakes. NEVER invent nonexistent kanji compounds or complete nonsense words.
    4. NO DUPLICATE OPTIONS: All 4 options (A, B, C, D) MUST be strictly distinct strings. Do not duplicate the correct answer.
    5. NO MISSING CONTEXT: For Reading and Listening, you MUST comprehensively generate the full textual stimulus inside `passage_text` or `dialogue_script`. Do not just ask a question about a non-existent passage.
    6. PROPER BLANK FORMATTING: Whenever a question requires a blank space for the student to fill in, you MUST use full-width Japanese parentheses with a full-width space inside: （　　）. DO NOT use regular empty spaces or underscores (except for the syntax scrambled sub-type which uses ＿＿　＿＿　★　＿＿).
    7. NO NEWLINE CHARACTERS IN SCRIPT: For Listening comprehension, you MUST generate the entire `dialogue_script` as a single, continuous continuous string. Do NOT use `\\n` or `\n` or any newline characters inside the script, as it breaks the Text-to-Speech engine. Use simple punctuation (periods, commas, etc.) to separate sentences and speakers (e.g., "男：やあ。女：こんにちは。").
    
    CRITICAL: For each generated question, you MUST set "section": "{section}", "sub_type": "{sub_type}", AND include all of the required schema fields!
    CRITICAL DIVERSITY REQUIREMENT: You MUST ensure high diversity across questions. DO NOT repeat the exact same grammar patterns, vocabulary words, or scenarios. Each of the {count} questions must test completely distinct items.
    
    IMPORTANT SYSTEM INSTRUCTION: You MUST use the provided tool/function to output your response perfectly matching the schema. DO NOT output raw markdown or ```json text blocks in your generation.
    """
        
    # 6. GENERATE
    from app.models.schemas import GeneratedQuestionBatch
    structured_llm = llm.with_structured_output(GeneratedQuestionBatch)
    response_batch = structured_llm.invoke(system_prompt)
    
    questions = []
    if response_batch and response_batch.questions:
        for q in response_batch.questions:
            q.section = section
            q.sub_type = sub_type
            questions.append(q)
    
    return {
        "generated_questions": questions,
        "retry_count": current_count + 1,
        "generation_mode": "standard",
        "current_data_payload": data_list
    }