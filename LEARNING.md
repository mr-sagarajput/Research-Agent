# Learning Notes: Free Local Research Agent

A friendly reference notebook documenting Python concepts, AI terms, and architectural lessons learned during this project.

---

## Step 1 & 2: Foundations & Setup

### 1. Variables
- **What it means:** A variable is a named storage container for data. You give it a name and assign a value using the equals sign (`=`).
- **Example from `config.py`:**
  ```python
  PAGE_LIMIT = 4
  ```
  Here, `PAGE_LIMIT` is a variable holding the integer number `4`. By writing it in ALL_CAPS, we follow Python convention to indicate it is a **constant** (a value meant to remain fixed).

### 2. Imports (`import`)
- **What it means:** Python comes with basic tools, but you can bring in extra toolkits (libraries or modules) using `import`. 
- **Example from `config.py`:**
  ```python
  from pathlib import Path
  ```
  This brings in Python's modern `Path` tool, which allows us to work with folders and file paths safely on any operating system (Windows, Mac, or Linux).

### 3. Strings & Numbers
- **String (`str`):** Text wrapped in quotes, like `"qwen3:1.7b"` or `"output"`.
- **Integer (`int`):** A whole number without a decimal point, such as `4` or `4000`.
- **Float (`float`):** A number with a decimal point, such as `1.5` in `REQUEST_DELAY_SECONDS = 1.5`.
- **Boolean (`bool`):** A true-or-false flag, such as `EXPORT_DOCX = False`.

### 4. Quantization
- **What it means:** A mathematical technique that compresses neural network weights (e.g. from 16-bit numbers to 4-bit numbers) so that a large model fits into limited RAM (like our 4 GB system) with minimal loss of accuracy.

### 5. Robots.txt
- **What it means:** A public text file hosted on a website root (e.g., `https://example.com/robots.txt`) specifying rules about which parts of the site automated crawlers and bots are permitted or forbidden to read.

---

## Step 3: Functions, Error Handling, and LLM Communication

### 6. Functions (`def`)
- **What it means:** A reusable block of code that performs a specific task. You define it once using the `def` keyword, give it a name, and call it whenever you need that task done.
- **Example from `modules/llm.py`:**
  ```python
  def remove_thinking_tags(text: str) -> str:
      cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
      return cleaned.strip()
  ```

### 7. Parameters & Return Values
- **Parameter:** The input data you pass into a function so it has something to work with (e.g. `prompt` and `system_prompt` in `query_llm`).
- **Return Value (`return`):** The final result that the function sends back to the code that called it (e.g. the cleaned response string).

### 8. Try / Except (Exception Handling)
- **What it means:** A safety net in Python. It tells Python: *"Try to run this code, but if an error occurs (such as a lost connection), do not crash the entire program; jump to the `except` block and handle the problem gracefully."*
- **Example from `modules/llm.py`:**
  ```python
  try:
      response = client.generate(...)
      return response.get("response", "")
  except Exception as error:
      print(f"[Error in LLM module]: {error}")
      return ""
  ```

### 9. Regular Expressions (`re`)
- **What it means:** A search pattern syntax used to find and manipulate specific text structures. In our case, `r"<think>.*?</think>"` finds any opening tag `<think>`, everything in between (`.*?`), and the closing tag `</think>` so we can strip it away cleanly.

---

## Step 4: Search, Data Structures, and Polite Crawling

### 10. Lists (`list`)
- **What it means:** An ordered collection of items wrapped in square brackets `[...]`. Items can be strings, numbers, or even other data structures.
- **Example from `modules/search.py`:**
  ```python
  queries = ["python basics", "python tutorial"]
  ```

### 11. Dictionaries (`dict`)
- **What it means:** A collection of key-value pairs wrapped in curly braces `{...}`. You look up information using a named key (like a word in a dictionary) instead of an index number.
- **Example from `modules/search.py`:**
  ```python
  result = {
      "title": "Welcome to Python.org",
      "url": "https://www.python.org/"
  }
  ```
  Here, `result["title"]` gives you the page title.

### 12. `for` Loops
- **What it means:** A loop that repeats an action for each item in a collection (list, lines of text, etc.).
- **Example from `modules/search.py`:**
  ```python
  for item in search_generator:
      title = item.get("title", "No Title")
  ```

### 13. Fallback Pattern
- **What it means:** A software design strategy where you provide a backup plan if the primary option fails. For instance, our code tries to import `ddgs` first; if not installed, it falls back to `duckduckgo_search`. Similarly, if the LLM fails to generate queries, we fall back to using the raw topic directly.

---

## Step 3 Update: Multi-stage Startup Verification & Guard Clauses

### 14. Guard Clause
- **What it means:** A programming pattern where you check for error conditions at the very beginning of a function and exit immediately if something is wrong. This keeps the rest of the code clean and prevents nested `if` statements.
- **Example from `modules/llm.py`:**
  ```python
  if not check_ollama_status():
      return ""
  ```

### 15. The `any()` Function
- **What it means:** A built-in Python function that checks an entire collection and returns `True` if at least one item satisfies a condition, or `False` if none do.
- **Example from `modules/llm.py`:**
  ```python
  model_found = any(m == MODEL_NAME for m in installed_models)
  ```

### 16. `getattr()` (Safe Attribute Access)
- **What it means:** In Python, objects may have different attributes depending on library versions (e.g. `item.model` vs `item.name`). `getattr(item, "model", None)` safely checks if `.model` exists; if not, it returns `None` instead of throwing an error.

---

## Secret Management & Environment Variables

### 17. Environment Variables (`.env`)
- **What it means:** A secure way to store private settings—like passwords, tokens, and API keys—outside of your actual Python code files.
- **Example from `.env`:**
  ```text
  GOOGLE_API_KEY=AIzaSy...
  ```
- **Why it matters:** If you share your code or upload it to GitHub, you do not want your private secret keys included. Python reads `.env` dynamically using packages like `python-dotenv` or `os.environ`.

### 18. API Key
- **What it means:** A unique digital passcode provided by a service (like Google AI Studio) that identifies your project and gives your script permission to communicate with their AI models.

---

## Provider Abstraction & Exponential Backoff

### 19. Provider Abstraction (Adapter Pattern)
- **What it means:** A software design technique where your core program communicates with a single standard function (like `query_llm()`), while the underlying system can swap between completely different services (e.g. cloud-based Google Gemini vs offline local Ollama) based on a simple configuration switch (`LLM_PROVIDER`), without rewriting any other part of the project.

### 20. Exponential Backoff
- **What it means:** An error recovery strategy where a program pauses before retrying a failed network request, doubling the waiting time on each consecutive failure (e.g., waiting 2 seconds, then 4 seconds, then 8 seconds). This prevents overwhelming servers when rate limits (429 errors) occur.

---

## Step 5: Web Page Fetching, URL Encoding, and HTML Parsing

### 21. Percent-Encoding (URL Encoding)
- **What it means:** Standard web protocols (HTTP/HTTPS) only permit ASCII characters in URLs. When a link contains non-ASCII characters (such as Hindi / Devanagari script `कृत्रिम_बुद्धि`), Python uses `urllib.parse.quote()` to convert each Unicode character into a percentage symbol followed by hexadecimal numbers (e.g., `%E0%A4%95...`), ensuring the web server can read it without errors.

### 22. HTML Element Decomposition (`element.decompose()`)
- **What it means:** A technique in the BeautifulSoup library that completely deletes unwanted HTML tags (such as JavaScript `<script>`, navigation menus `<nav>`, and CSS `<style>`) from memory before extracting readable article text. This prevents clutter and code snippets from polluting our research summaries.

### 23. Crawler Politeness & Etiquette
- **What it means:** Best practices for ethical web automation:
  1. **User-Agent:** Announcing who your bot is in request headers.
  2. **Robots.txt:** Checking the website's public rules before fetching.
  3. **Delays (`time.sleep`):** Adding pauses between requests so you never flood or slow down web servers.

---

## Step 6: Pipeline Orchestration, Argument Parsing, and Deduplication

### 24. Command-Line Arguments (`argparse`)
- **What it means:** A built-in Python module that lets users pass flags and options when launching a script from the terminal (e.g. `python main.py --test` or `python main.py --topic "AI Ethics"`).
- **Example from `main.py`:**
  ```python
  parser.add_argument("--test", action="store_true", help="Run self-test mode")
  ```

### 25. Sets (`set`) for Deduplication
- **What it means:** A collection of unique elements with no duplicates. Checking `if url not in seen_urls:` is extremely fast and ensures the agent never visits or processes the same web link twice during a single research run.
- **Example from `main.py`:**
  ```python
  seen_urls = set()
  if url not in seen_urls:
      seen_urls.add(url)
      candidate_urls.append(item)
  ```

### 26. Resilience / Graceful Skip
- **What it means:** Real-world web crawlers encounter broken links, paywalls, and HTTP 403 (Forbidden) responses. Our pipeline catches these skips gracefully, logs the reason in English, and automatically moves to the next candidate URL without interrupting or crashing the research session.

---

## Step 7: Output Persistence, File Handling, and Document Generation

### 27. File I/O (`open()`)
- **What it means:** "I/O" stands for Input/Output. In Python, file I/O refers to reading data from files or writing new data to disk. The built-in `open()` function takes the target file path and a mode—such as `'w'` for writing (creating a new file or overwriting an existing one), `'r'` for reading, or `'a'` for appending.
- **Why `encoding='utf-8'` is essential:** By default, operating systems like Windows may use localized legacy character encodings (e.g., Windows-1252), which can scramble non-ASCII characters or cause crashes when saving international text. Specifying `encoding='utf-8'` ensures universal compatibility, allowing English, Hindi (Devanagari script), emojis, and special symbols to save cleanly without corruption.
- **Example:**
  ```python
  with open("output/research_report.md", "w", encoding="utf-8") as file:
      file.write("# Research Report\n\nContent goes here...")
  ```

### 28. Context Managers (`with` Statement)
- **What it means:** A context manager is a Python construct that automatically manages external resources—like files, network sockets, or database connections. It guarantees proper setup before you enter a code block and reliable cleanup (teardown) when you exit, even if an unexpected error or exception occurs inside the block.
- **How the `with` statement works:** When opening a file with `with open(...) as f:`, Python automatically calls `f.close()` the exact moment code execution leaves the indented block.
- **Why it matters:** Without `with`, you would have to remember to manually call `file.close()`. If your script crashed before reaching `.close()`, the file could remain locked by the operating system, leak memory, or lose unsaved buffered data. The `with` statement makes resource management foolproof.
- **Example:**
  ```python
  # Safe resource management: the file closes automatically when the block finishes
  with open("output/notes.txt", "w", encoding="utf-8") as f:
      f.write("Important research bullet points")
  # At this point, the file is already closed and safely saved to disk
  ```

### 29. String Formatting (f-strings)
- **What it means:** Introduced in Python 3.6, formatted string literals (commonly called **f-strings**) are strings prefixed with the letter `f` or `F` (e.g., `f"Hello, {name}!"`). They allow you to embed Python variables, expressions, or function calls directly inside string literals by enclosing them in curly braces `{}`.
- **Why it matters:** Prior to f-strings, Python relied on older formatting styles such as `%` formatting (`"%s is %d" % (name, count)`) or `.format()` (`"{} is {}".format(name, count)`), which were verbose and prone to ordering mistakes. F-strings make code dramatically more readable, concise, and faster to execute.
- **Example:**
  ```python
  topic = "Artificial Intelligence"
  page_count = 4
  status = f"Completed research on '{topic}' across {page_count} web pages."
  print(status)
  # Output: Completed research on 'Artificial Intelligence' across 4 web pages.
  ```

### 30. Document Automation (`python-docx` Document Structure)
- **What it means:** Document automation is the programmatic creation and formatting of word processor files (like Microsoft Word `.docx` documents) using code instead of manual point-and-click editing. The `python-docx` library allows Python scripts to construct Word documents by manipulating a hierarchical object tree:
  1. **`Document`**: The top-level document object representing the entire file.
  2. **Headings (`doc.add_heading(...)`)**: Structural titles and section headers styled with standard Word heading levels (`level=1`, `level=2`, etc.).
  3. **Paragraphs (`doc.add_paragraph(...)`)**: Distinct blocks of text or bullet points (`style='List Bullet'`).
  4. **Runs (`paragraph.add_run(...)`)**: Contiguous chunks of text within a paragraph that share identical styling (such as bold, italics, font size, or color).
- **Example:**
  ```python
  from docx import Document

  # 1. Create a new document in memory
  doc = Document()

  # 2. Add document title and section headings
  doc.add_heading("Automated Research Report", level=1)
  doc.add_heading("Executive Summary", level=2)

  # 3. Add text paragraphs and styled runs
  p = doc.add_paragraph("This report was compiled by our ")
  run = p.add_run("Free Research Agent")
  run.bold = True
  p.add_run(" using verified web sources.")

  # 4. Add structured bullet points
  doc.add_paragraph("DuckDuckGo search queries", style="List Bullet")
  doc.add_paragraph("Polite scraping with robots.txt compliance", style="List Bullet")

  # 5. Save the file to disk
  doc.save("output/report.docx")
  ```

---

## PDF Generation & Flowable Layouts (ReportLab)

### 31. Document Templates (`SimpleDocTemplate`)
- **What it means:** A layout engine in ReportLab that manages page geometry (paper size, margins, page breaks, and headers/footers) so your document formats cleanly across multiple pages without manual coordinate calculations.
- **Example from `modules/report.py`:**
  ```python
  doc = SimpleDocTemplate(str(output_filepath), pagesize=letter, leftMargin=54, rightMargin=54)
  ```

### 32. Flowables (`Paragraph`, `Spacer`, `Table`)
- **What it means:** Independent visual building blocks in ReportLab that "flow" onto the page from top to bottom. If a flowable does not fit on the current page, ReportLab automatically creates a new page and continues placing elements.
- **Example from `modules/report.py`:**
  ```python
  story.append(Paragraph("Executive Summary", section_heading_style))
  story.append(Spacer(1, 10))
  story.append(summary_table)
  ```

### 33. Line Leading
- **What it means:** In digital typography, "leading" (pronounced *led-ing*) is the vertical space between consecutive lines of text. For example, a font size of 10 points with a leading of 14 points ensures comfortable line spacing and readability.

### 34. XML Text Escaping (`html.escape()`)
- **What it means:** ReportLab's `Paragraph` engine uses an internal XML-like parser to support styling tags like `<b>` and `<a>`. If raw article text contains characters like `<` or `&`, the parser can crash. Using `html.escape(text)` converts `<` into `&lt;` and `&` into `&amp;` so the PDF engine renders text safely without errors.
