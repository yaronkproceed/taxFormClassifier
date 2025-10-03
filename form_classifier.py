#!/usr/bin/env python3
"""
Form Classifier Application
Processes PDF forms and classifies them using Gemini 2.5 Flash Lite
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import PyPDF2
import google.generativeai as genai
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT, USER_PROMPT
from datetime import datetime
from rapidfuzz import fuzz

# Load environment variables
load_dotenv()

@dataclass
class FormConfig:
    """Configuration for expected form data"""
    form_number: str
    expected_title_1: str
    expected_title_2: str
    expected_pages: int

@dataclass
class ClassificationResult:
    """Result of form classification"""
    filename: str
    form_number: str
    form_title: str
    page_count: int
    confidence: str  # Changed to string: "High", "Medium", or "Low"
    llm_response: Dict
    is_verified: bool
    token_usage: Dict
    error: Optional[str] = None

class FormClassifier:
    """Main classifier class"""

    def __init__(self, api_key: str, config_file: str):
        """
        Initialize the classifier

        Args:
            api_key: Google Gemini API key
            config_file: Path to JSON file containing expected form data
        """
        self.api_key = api_key
        self.config_file = config_file
        self.form_configs = self._load_config()
        self._setup_gemini()

    def _load_config(self) -> Dict[str, FormConfig]:
        """Load form configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            configs = {}
            for item in config_data:
                config = FormConfig(
                    form_number=item['form_number'],
                    expected_title_1=item['expected_title_1'],
                    expected_title_2=item['expected_title_2'],
                    expected_pages=item['expected_pages']
                )
                configs[item['form_number']] = config

            print(f"Loaded {len(configs)} form configurations")
            return configs

        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")

    def _setup_gemini(self):
        """Setup Gemini API"""
        genai.configure(api_key=self.api_key)
        # Note: Model instance created per file in classify_form()

    def load_pdf_file(self, pdf_path: str):
        """
        Load PDF file for Gemini upload

        Args:
            pdf_path: Path to PDF file

        Returns:
            File object ready for upload
        """
        try:
            return genai.upload_file(pdf_path)
        except Exception as e:
            raise ValueError(f"Error loading PDF file {pdf_path}: {e}")

    def classify_form(self, pdf_path: str, filename: str) -> ClassificationResult:
        """
        Classify a form using Gemini

        Args:
            pdf_path: Path to PDF file
            filename: Original filename for reference

        Returns:
            ClassificationResult object
        """
        # Use prompts from separate file
        system_prompt = SYSTEM_PROMPT
        user_prompt = USER_PROMPT
        
        uploaded_file = None  # Track uploaded file for cleanup

        try:
            # Define safety settings to reduce sensitivity to PII in forms
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            ]

            # Create fresh model instance with safety settings for form processing
            model = genai.GenerativeModel(
                'gemini-2.5-flash-lite',
                safety_settings=safety_settings
            )

            # Upload the PDF file
            uploaded_file = self.load_pdf_file(pdf_path)

            # Generate content with the uploaded file
            response = model.generate_content(
                [system_prompt, uploaded_file, user_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=1,         # Minimum temperature for maximum consistency
                    top_p=0.95,               # Nucleus sampling for focused output
                    top_k=10,                 # Only consider the most probable token
                    max_output_tokens=1500,  # Reasonable limit for structured JSON
                    candidate_count=1,       # Only generate one response
                    stop_sequences=None,     # No specific stop sequences
                )
            )

            # Parse JSON response with improved error handling
            json_text = response.text.strip()

            # Handle various markdown code block formats
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            if json_text.endswith('```'):
                json_text = json_text[:-3]
            elif json_text.startswith('```'):
                json_text = json_text[3:]
                if json_text.endswith('```'):
                    json_text = json_text[:-3]

            # Additional cleanup for any remaining markdown
            json_text = json_text.replace('```', '').strip()

            try:
                llm_response = json.loads(json_text)
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to extract JSON from the response
                import re
                json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
                if json_match:
                    llm_response = json.loads(json_match.group())
                else:
                    raise ValueError(f"Could not parse JSON from response: {json_text[:200]}...")

            # Get token usage
            token_usage = {
                'input_tokens': response.usage_metadata.prompt_token_count,
                'output_tokens': response.usage_metadata.candidates_token_count,
                'total_tokens': response.usage_metadata.total_token_count
            }

            # Extract values from nested structure
            form_number = llm_response.get('form_classification', {}).get('form_number', {}).get('value', '')
            form_title = llm_response.get('form_classification', {}).get('form_title', {}).get('value', '')
            page_count = llm_response.get('form_classification', {}).get('page_count', {}).get('value', 0)
            confidence = llm_response.get('form_classification', {}).get('form_number', {}).get('confidence_level', 'Low')

            is_verified = self._verify_classification(form_number, form_title, page_count)

            return ClassificationResult(
                filename=filename,
                form_number=form_number,
                form_title=form_title,
                page_count=page_count,
                confidence=confidence,
                llm_response=llm_response,
                is_verified=is_verified,
                token_usage=token_usage
            )

        except Exception as e:
            # Enhanced error reporting with detailed API error information
            error_details = []

            # Basic error info
            error_details.append(f"Exception Type: {type(e).__name__}")
            error_details.append(f"Error Message: {str(e)}")

            # Try to get more detailed information from the model response
            try:
                # Check if response object exists and has error details
                if 'response' in locals():
                    if hasattr(response, 'prompt_feedback'):
                        error_details.append(f"Prompt Feedback: {response.prompt_feedback}")
                        # Check for blocked content reasons
                        if hasattr(response.prompt_feedback, 'block_reason'):
                            error_details.append(f"  Block Reason: {response.prompt_feedback.block_reason}")
                    if hasattr(response, 'candidates') and response.candidates:
                        for i, candidate in enumerate(response.candidates):
                            finish_reason = getattr(candidate, 'finish_reason', 'unknown')
                            error_details.append(f"Candidate {i}: finish_reason={finish_reason}")

                            if finish_reason == 2:  # SAFETY
                                error_details.append(f"  SAFETY FILTER TRIGGERED - This is likely due to PII detection")
                                error_details.append(f"  NOTE: Current safety settings: BLOCK_NONE (all filters disabled)")
                                error_details.append(f"  NOTE: If still blocked: The content may violate API terms of service at infrastructure level")
                                error_details.append(f"  NOTE: Solution: Check PDF for content that violates Gemini API terms:")
                                error_details.append(f"       • Malicious or harmful content")
                                error_details.append(f"       • Inappropriate images or text")
                                error_details.append(f"       • Content against API policies")

                            if hasattr(candidate, 'finish_message'):
                                error_details.append(f"  Finish Message: {candidate.finish_message}")
                            if hasattr(candidate, 'safety_ratings'):
                                error_details.append(f"  Safety Ratings: {candidate.safety_ratings}")

                    # Check for safety settings that were applied
                    if hasattr(model, '_safety_settings'):
                        error_details.append(f"Safety Settings Used: {model._safety_settings}")
            except Exception as inner_e:
                error_details.append(f"Could not extract response details: {inner_e}")

            # Try to get generation config details
            try:
                error_details.append(f"Model Used: {model.model_name}")
                error_details.append(f"Generation Config: temp={generation_config.temperature}, top_p={generation_config.top_p}, top_k={generation_config.top_k}")
            except:
                pass

            # Try to get file upload info
            try:
                error_details.append(f"File: {pdf_path}")
                error_details.append(f"Uploaded File: {uploaded_file.name if uploaded_file else 'None'}")
            except:
                pass

            # Format the complete error report
            detailed_error = "\n".join([f"  {line}" for line in error_details])

            print(f"DETAILED ERROR REPORT for {filename}:")
            print("=" * 60)
            for line in error_details:
                print(f"  {line}")
            print("=" * 60)

            return ClassificationResult(
                filename=filename,
                form_number="",
                form_title="",
                page_count=0,
                confidence="Low",
                llm_response={},
                is_verified=False,
                token_usage={},
                error=detailed_error
            )
        
        finally:
            # Clean up the uploaded file to prevent carryover between files
            if uploaded_file:
                try:
                    genai.delete_file(uploaded_file.name)
                    print(f"Cleaned up uploaded file for {filename}")
                except Exception as cleanup_error:
                    print(f"Warning: Could not clean up file {filename}: {cleanup_error}")
                    # Don't raise the error, just log it

    def _verify_classification(self, form_number: str, form_title: str, page_count: int) -> bool:
        """
        Verify classification against expected values
        Uses dual title matching with both "contains" and fuzzy matching

        Args:
            form_number: Detected form number
            form_title: Detected form title
            page_count: Detected page count

        Returns:
            True if classification is verified
        """
        if form_number not in self.form_configs:
            return False

        expected = self.form_configs[form_number]
        
        # Normalize strings for comparison
        extracted_title = form_title.strip()
        expected_title_1 = expected.expected_title_1.strip()
        expected_title_2 = expected.expected_title_2.strip()

        # Method 1: "Contains" matching - check if either expected title is contained in extracted title
        contains_match_1 = expected_title_1 in extracted_title
        contains_match_2 = expected_title_2 in extracted_title
        
        # Method 2: Fuzzy matching - check if similarity is above 85% threshold
        fuzzy_score_1 = fuzz.partial_ratio(expected_title_1, extracted_title)
        fuzzy_score_2 = fuzz.partial_ratio(expected_title_2, extracted_title)
        fuzzy_threshold = 85
        
        fuzzy_match_1 = fuzzy_score_1 >= fuzzy_threshold
        fuzzy_match_2 = fuzzy_score_2 >= fuzzy_threshold
        
        # Title matches if EITHER title matches using EITHER method
        title_match = contains_match_1 or contains_match_2 or fuzzy_match_1 or fuzzy_match_2
        
        # Page count must match exactly
        page_match = page_count == expected.expected_pages

        return title_match and page_match

    def process_folder(self, folder_path: str) -> List[ClassificationResult]:
        """
        Process all PDF files in a folder

        Args:
            folder_path: Path to folder containing PDF files

        Returns:
            List of ClassificationResult objects
        """
        folder = Path(folder_path)
        results = []

        if not folder.exists():
            raise ValueError(f"Folder {folder_path} does not exist")

        pdf_files = list(folder.glob("*.pdf"))

        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return results

        print(f"Processing {len(pdf_files)} PDF files...")

        for pdf_file in pdf_files:
            print(f"Processing: {pdf_file.name}")

            try:
                # Classify the form directly with PDF file
                result = self.classify_form(str(pdf_file), pdf_file.name)
                results.append(result)

            except Exception as e:
                result = ClassificationResult(
                    filename=pdf_file.name,
                    form_number="",
                    form_title="",
                    page_count=0,
                    confidence="Low",
                    llm_response={},
                    is_verified=False,
                    token_usage={},
                    error=str(e)
                )
                results.append(result)

        return results

    def save_results(self, results: List[ClassificationResult], output_file: str):
        """
        Save results to output file

        Args:
            results: List of ClassificationResult objects
            output_file: Path to output file
        """
        output_data = []

        for result in results:
            output_data.append({
                "filename": result.filename,
                "form_number": result.form_number,
                "form_title": result.form_title,
                "page_count": result.page_count,
                "confidence": result.confidence,
                "is_verified": result.is_verified,
                "token_usage": result.token_usage,
                "llm_response": result.llm_response,
                "error": result.error
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to {output_file}")

    def save_stats(self, results: List[ClassificationResult], stats_file: str = "classification_stats.html"):
        """
        Save statistics table to HTML file for better readability

        Args:
            results: List of ClassificationResult objects
            stats_file: Path to statistics file (now HTML format)
        """
        # Read existing stats if file exists
        existing_rows = []
        headers = [
            "File Name", "Date", "Form Type", "Conf (Type)", "Title", "Conf (Title)",
            "Pages", "Conf (Pages)", "Input Tokens", "Output Tokens", "Expected Title", "Expected Pages", "Success"
        ]

        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if '<table' in content and '<tbody>' in content:
                    # Parse existing HTML table rows
                    import re
                    from bs4 import BeautifulSoup

                    try:
                        soup = BeautifulSoup(content, 'html.parser')
                        table = soup.find('table')

                        if table and table.find('tbody'):
                            existing_rows = []
                            rows = table.find('tbody').find_all('tr')

                            # Validate that we have a proper table structure
                            if rows and len(rows) > 0:
                                print(f"Found {len(rows)} existing table rows in HTML file")

                                for row in rows:
                                    cells = row.find_all('td')
                                    if len(cells) >= len(headers):
                                        row_data = []
                                        for cell in cells:
                                            # Extract text and clean it
                                            text = cell.get_text(strip=True)
                                            # Handle confidence values that might have classes
                                            if 'confidence-' in str(cell):
                                                row_data.append(text)  # Just the number
                                            else:
                                                row_data.append(text)

                                        if row_data and any(data.strip() for data in row_data):
                                            existing_rows.append(row_data)

                                print(f"Loaded {len(existing_rows)} existing rows from {stats_file}")
                            else:
                                print("No valid table rows found in existing HTML file")
                                existing_rows = []
                        else:
                            print("No table or tbody found in existing HTML file")
                            existing_rows = []
                    except Exception as parse_error:
                        print(f"Error parsing existing HTML file: {parse_error}")
                        existing_rows = []

            except Exception as e:
                print(f"Warning: Could not read existing stats file: {e}")
                existing_rows = []

        # Add new rows
        new_rows = []
        for result in results:
            # Get expected values from config
            expected_title = ""
            expected_pages = ""

            if result.form_number in self.form_configs:
                # Display both expected titles separated by " OR "
                expected_title = f"{self.form_configs[result.form_number].expected_title_1} OR {self.form_configs[result.form_number].expected_title_2}"
                expected_pages = str(self.form_configs[result.form_number].expected_pages)

            # Extract values from llm_response
            llm_data = result.llm_response.get('form_classification', {})

            form_type_conf = llm_data.get('form_number', {}).get('confidence_level', 0)
            title_conf = llm_data.get('form_title', {}).get('confidence_level', 0)
            pages_conf = llm_data.get('page_count', {}).get('confidence_level', 0)

            # Get token usage data
            input_tokens = result.token_usage.get('input_tokens', 0)
            output_tokens = result.token_usage.get('output_tokens', 0)

            # Create row
            row = [
                result.filename,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                result.form_number,
                str(form_type_conf),
                result.form_title,
                str(title_conf),
                str(result.page_count),
                str(pages_conf),
                str(input_tokens),
                str(output_tokens),
                expected_title,
                expected_pages,
                "Yes" if result.is_verified else "No"
            ]
            new_rows.append(row)

        # Combine existing and new rows
        all_rows = existing_rows + new_rows

        # Check if file exists to determine if we need to create new or append
        file_exists = os.path.exists(stats_file)

        if file_exists:
            # Parse existing HTML and append new rows
            try:
                from bs4 import BeautifulSoup

                with open(stats_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')

                # Update timestamp
                timestamp_div = soup.find('div', class_='timestamp')
                if timestamp_div:
                    timestamp_div.string = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                # Update summary
                summary_div = soup.find('div', class_='stats-summary')
                if summary_div:
                    verified_count = sum(1 for r in all_rows if r[12] == "Yes")
                    failed_count = sum(1 for r in all_rows if r[12] == "No")
                    summary_div.clear()
                    summary_div.append(BeautifulSoup(f'<strong>Summary:</strong> {len(all_rows)} total classifications | <strong>Verified:</strong> {verified_count} | <strong>Failed:</strong> {failed_count}', 'html.parser'))

                # Find tbody and append new rows
                tbody = soup.find('tbody')
                if tbody:
                    # Remove existing rows if we're rebuilding from scratch
                    tbody.clear()

                    # Add all rows (existing + new)
                    for row in all_rows:
                        tr = soup.new_tag('tr')

                        # File name
                        td = soup.new_tag('td')
                        td.string = row[0]
                        tr.append(td)

                        # Date
                        td = soup.new_tag('td')
                        td.string = row[1]
                        tr.append(td)

                        # Form type
                        td = soup.new_tag('td')
                        td.string = row[2]
                        tr.append(td)

                        # Confidence (Type) with color coding
                        conf_type = row[3].strip() if row[3] else "Low"
                        conf_class = "confidence-high" if conf_type == "High" else "confidence-medium" if conf_type == "Medium" else "confidence-low"
                        td = soup.new_tag('td', **{'class': conf_class})
                        td.string = row[3]
                        tr.append(td)

                        # Title (handle Hebrew text)
                        td = soup.new_tag('td', style='max-width: 200px; word-wrap: break-word;')
                        td.string = row[4]
                        tr.append(td)

                        # Confidence (Title) with color coding
                        conf_title = row[5].strip() if row[5] else "Low"
                        conf_class = "confidence-high" if conf_title == "High" else "confidence-medium" if conf_title == "Medium" else "confidence-low"
                        td = soup.new_tag('td', **{'class': conf_class})
                        td.string = row[5]
                        tr.append(td)

                        # Pages
                        td = soup.new_tag('td')
                        td.string = row[6]
                        tr.append(td)

                        # Confidence (Pages) with color coding
                        conf_pages = row[7].strip() if row[7] else "Low"
                        conf_class = "confidence-high" if conf_pages == "High" else "confidence-medium" if conf_pages == "Medium" else "confidence-low"
                        td = soup.new_tag('td', **{'class': conf_class})
                        td.string = row[7]
                        tr.append(td)

                        # Input tokens
                        td = soup.new_tag('td')
                        td.string = row[8]
                        tr.append(td)

                        # Output tokens
                        td = soup.new_tag('td')
                        td.string = row[9]
                        tr.append(td)

                        # Expected title (handle Hebrew text)
                        td = soup.new_tag('td', style='max-width: 200px; word-wrap: break-word;')
                        td.string = row[10]
                        tr.append(td)

                        # Expected pages
                        td = soup.new_tag('td')
                        td.string = row[11]
                        tr.append(td)

                        # Success with color coding
                        success_class = "success-yes" if row[12] == "Yes" else "success-no"
                        td = soup.new_tag('td', **{'class': success_class})
                        strong = soup.new_tag('strong')
                        strong.string = row[12]
                        td.append(strong)
                        tr.append(td)

                        tbody.append(tr)

                # Write back the modified HTML
                with open(stats_file, 'w', encoding='utf-8') as f:
                    try:
                        # Clean up any None values that might cause issues
                        for element in soup.find_all():
                            if element.string is None and not element.contents:
                                element.string = ""

                        # Use prettify() instead of str() for better HTML formatting
                        f.write(soup.prettify())
                        print(f"Successfully updated existing HTML file with {len(all_rows)} total rows")
                    except Exception as write_error:
                        print(f"Error writing HTML file: {write_error}")
                        print("Attempting to recreate HTML file from scratch...")
                        raise write_error

            except Exception as e:
                print(f"Error updating existing HTML file: {e}")
                print("Creating new HTML file instead...")
                file_exists = False

        if not file_exists:
            # Create new HTML file
            with open(stats_file, 'w', encoding='utf-8') as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Form Classification Statistics</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
        th { background-color: #f2f2f2; font-weight: bold; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f0f8ff; }
        .success-yes { background-color: #d4edda; color: #155724; }
        .success-no { background-color: #f8d7da; color: #721c24; }
        .confidence-high { background-color: #d1ecf1; }
        .confidence-medium { background-color: #fff3cd; }
        .confidence-low { background-color: #f8d7da; }
        .timestamp { color: #666; font-size: 0.9em; }
        .stats-summary { background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>📊 Form Classification Statistics</h1>
    <div class="timestamp">Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</div>

    <div class="stats-summary">
        <strong>Summary:</strong> """ + str(len(all_rows)) + """ total classifications |
        <strong>Verified:</strong> """ + str(sum(1 for r in all_rows if r[12] == "Yes")) + """ |
        <strong>Failed:</strong> """ + str(sum(1 for r in all_rows if r[12] == "No")) + """
    </div>

    <table>
        <thead>
            <tr>""")

                for header in headers:
                    f.write(f"<th>{header}</th>")

                f.write("""
            </tr>
        </thead>
        <tbody>""")

                for row in all_rows:
                    f.write("<tr>")

                    # File name
                    f.write(f"<td>{row[0]}</td>")

                    # Date
                    f.write(f"<td>{row[1]}</td>")

                    # Form type
                    f.write(f"<td>{row[2]}</td>")

                    # Confidence (Type) with color coding
                    conf_type = row[3].strip() if row[3] else "Low"
                    conf_class = "confidence-high" if conf_type == "High" else "confidence-medium" if conf_type == "Medium" else "confidence-low"
                    f.write(f"<td class='{conf_class}'>{row[3]}</td>")

                    # Title (handle Hebrew text)
                    f.write(f"<td style='max-width: 200px; word-wrap: break-word;'>{row[4]}</td>")

                    # Confidence (Title) with color coding
                    conf_title = row[5].strip() if row[5] else "Low"
                    conf_class = "confidence-high" if conf_title == "High" else "confidence-medium" if conf_title == "Medium" else "confidence-low"
                    f.write(f"<td class='{conf_class}'>{row[5]}</td>")

                    # Pages
                    f.write(f"<td>{row[6]}</td>")

                    # Confidence (Pages) with color coding
                    conf_pages = row[7].strip() if row[7] else "Low"
                    conf_class = "confidence-high" if conf_pages == "High" else "confidence-medium" if conf_pages == "Medium" else "confidence-low"
                    f.write(f"<td class='{conf_class}'>{row[7]}</td>")

                    # Input tokens
                    f.write(f"<td>{row[8]}</td>")

                    # Output tokens
                    f.write(f"<td>{row[9]}</td>")

                    # Expected title (handle Hebrew text)
                    f.write(f"<td style='max-width: 200px; word-wrap: break-word;'>{row[10]}</td>")

                    # Expected pages
                    f.write(f"<td>{row[11]}</td>")

                    # Success with color coding
                    success_class = "success-yes" if row[12] == "Yes" else "success-no"
                    f.write(f"<td class='{success_class}'><strong>{row[12]}</strong></td>")

                    f.write("</tr>")

                f.write("""
        </tbody>
    </table>

    <div style="margin-top: 20px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
        <strong>Instructions:</strong><br>
        • <strong>Green confidence cells</strong>: High confidence<br>
        • <strong>Yellow confidence cells</strong>: Medium confidence<br>
        • <strong>Orange confidence cells</strong>: Low confidence<br>
        • <strong>Green "Success"</strong>: Verified classification<br>
        • <strong>Red "Success"</strong>: Failed classification<br>
        • <strong>Token counts</strong>: API usage (Input/Output tokens)<br>
        • <strong>Data Persistence</strong>: New runs append to existing data, never overwrite<br>
        • Hebrew text is preserved and displayed correctly
    </div>
</body>
</html>""")

        print(f"Statistics updated in {stats_file} - open in browser for best viewing!")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Classify PDF forms using Gemini AI")
    parser.add_argument("folder", help="Path to folder containing PDF files")
    parser.add_argument("config", help="Path to JSON config file with expected form data")
    parser.add_argument("output", help="Path to output file for results")
    parser.add_argument("--api-key", help="Google Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--stats", help="Path to statistics file (default: classification_stats.html)", default="classification_stats.html")

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: Please provide API key via --api-key or GEMINI_API_KEY environment variable")
        return

    try:
        # Initialize classifier
        classifier = FormClassifier(api_key, args.config)

        # Process folder
        results = classifier.process_folder(args.folder)

        # Save results
        classifier.save_results(results, args.output)

        # Save statistics
        classifier.save_stats(results, args.stats)

        # Print summary
        verified_count = sum(1 for r in results if r.is_verified)
        total_count = len(results)
        error_count = sum(1 for r in results if r.error)

        print("=== SUMMARY ===")
        print(f"Total files processed: {total_count}")
        print(f"Verified classifications: {verified_count}")
        print(f"Failed classifications: {total_count - verified_count - error_count}")
        print(f"Errors: {error_count}")

        if verified_count > 0:
            total_tokens = sum(r.token_usage.get('total_tokens', 0) for r in results if r.token_usage)
            print(f"Total tokens used: {total_tokens}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()