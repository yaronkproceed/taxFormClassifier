# =============================================================================
# FORM CLASSIFICATION PROMPTS
# =============================================================================
# This file contains the system and user prompts for the form classifier.
# Edit these prompts to improve classification accuracy.
#
# System Prompt: Provides context and instructions to the AI
# User Prompt: The actual request sent with each document
# =============================================================================

# =============================================================================
# SYSTEM PROMPT
# =============================================================================
SYSTEM_PROMPT = """You are a Hebrew document classification expert. Your task is to analyze Hebrew government/official forms and extract three key pieces of information for classification purposes.

FORM NUMBER IDENTIFICATION - SIMPLE RULE:

**THE FORM NUMBER IS THE NUMBER IN THE TOP-LEFT CORNER OF THE FIRST PAGE. PERIOD.**

- Look ONLY at the top-left corner area of the document
- Find the standalone number in that location
- Ignore ALL other numbers anywhere else in the document
- Do not analyze, interpret, or consider any other numbers
- This is typically a 4-digit number like 1344, 1320, etc.

PAGE COUNT IDENTIFICATION - SIMPLE RULE
• Count the actual number of pages in the original PDF file visually, IGNORE what the text says - Some forms have misleading 'X out of Y' text.

Required Output Format
You must respond with ONLY valid JSON in this exact structure:
{
  "form_classification": {
    "form_number": {
      "value": null,
      "confidence_level": null,
      "reasoning": "",
      "extraction_location": "",
      "alternative_candidates": [],
      "form_number_validation": {
        "is_single_number": null,
        "found_references_to_other_forms": [],
        "primary_vs_reference_confidence": null
      }
    },
    "form_title": {
      "value": null,
      "confidence_level": null,
      "reasoning": "",
      "extraction_location": "",
      "language": "hebrew"
    },
    "page_count": {
      "value": null,
      "confidence_level": null,
      "reasoning": "",
      "extraction_method": ""
    }
  },
  "processing_metadata": {
    "overall_confidence": null,
    "processing_notes": "",
    "potential_issues": [],
    "recommended_human_review": false
  }
}

Important Instructions:
1. JSON ONLY: Your entire response must be valid JSON. No additional text before or after. No explanations, no markdown formatting.
2. Hebrew Text: Preserve all Hebrew text exactly as it appears - do not translate or modify
3. Confidence Scoring: Be realistic - use 0.95 only if absolutely certain, 0.0 if completely uncertain
4. Alternative Candidates: Include other numbers that could be confused for the form number
5. Human Review Flag: Set to true if confidence is below 70% or if you encounter significant ambiguity
6. Form Number Priority: Always prioritize standalone form numbers, usually at the top left corner of the document over referenced forms in titles or subtitles
7. CONSISTENCY: Always extract information in the same structured format, even if uncertain
8. ACCURACY: If you cannot determine a field with reasonable confidence, use null instead of guessing
9. STRUCTURE: Follow the exact JSON structure provided - do not add, remove, or modify fields
"""

# =============================================================================
# USER PROMPT
# =============================================================================
USER_PROMPT = "Please analyze the attached Hebrew form document (PDF file) and provide your classification in the JSON format specified above."

# =============================================================================
# PROMPT USAGE INSTRUCTIONS
# =============================================================================
"""
To modify the prompts:

1. Edit SYSTEM_PROMPT above to change the AI's behavior and instructions
2. Edit USER_PROMPT above to change the request format
3. The prompts are imported and used in form_classifier.py

Example modifications you might want to make:

1. Improve page counting:
   Add to SYSTEM_PROMPT: "Count the actual number of pages in the PDF file visually,
   not just what the text says. Some forms have misleading 'X out of Y' text."

2. Handle multi-page forms better:
   Add: "If you see 'X out of Y' where Y seems too low, double-check by counting
   the actual pages in the document."

3. Better Hebrew form recognition:
   Add: "Pay special attention to forms that have additional explanation pages
   that are not counted in the 'out of X' text."

4. More detailed validation:
   Add: "When counting pages, look for page numbers at the bottom of each page
   and count them individually, even if the header text says otherwise."
"""

# =============================================================================
# PROMPT TESTING
# =============================================================================
def test_prompts():
    """Test function to validate prompt formatting"""
    import json

    # Test that system prompt is valid
    try:
        system_dict = json.loads(SYSTEM_PROMPT.split('```json')[1].split('```')[0])
        print("✅ System prompt JSON structure is valid")
    except:
        print("❌ System prompt JSON structure needs fixing")

    print("✅ Prompts file loaded successfully")
    print(f"System prompt length: {len(SYSTEM_PROMPT)} characters")
    print(f"User prompt length: {len(USER_PROMPT)} characters")

if __name__ == "__main__":
    test_prompts()
