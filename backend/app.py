from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from main import run_analysis_from_flask

# ---------------------------------------
# PATH SETUP
# ---------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BACKEND_DIR, "uploads")
REPORT_FOLDER = os.path.join(BACKEND_DIR, "reports")
SCREENSHOT_FOLDER = os.path.join(REPORT_FOLDER, "screenshots")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ---------------------------------------
# FLASK APP (NEW: local templates/static)
# ---------------------------------------
app = Flask(
    __name__,
    template_folder="templates",  # now inside backend/templates
    static_folder="static"        # now inside backend/static
)

# Enable CORS for frontend (Firebase / anywhere)
CORS(app)

# ---------------------------------------
# ROUTES
# ---------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


# Serve case study screenshots
@app.route("/reports/screenshots/<path:filename>")
def report_screenshots(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)


# Main analysis endpoint
@app.route("/analyze", methods=["POST"])
def analyze():
    portfolio_url = request.form.get("portfolioUrl")
    resume = request.files.get("resume")

    if not portfolio_url:
        return jsonify({"error": "Portfolio URL missing"}), 400
    if not resume:
        return jsonify({"error": "Resume file missing"}), 400

    # Save resume safely
    safe_name = resume.filename.replace(" ", "_")
    resume_path = os.path.join(UPLOAD_FOLDER, safe_name)
    resume.save(resume_path)

    # Clear old JSON reports
    for file in os.listdir(REPORT_FOLDER):
        if file.endswith(".json"):
            try:
                os.remove(os.path.join(REPORT_FOLDER, file))
            except:
                pass

    # Run backend pipeline
    try:
        run_analysis_from_flask(portfolio_url, resume_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "analysis_complete"})


# Fetch all JSON reports
@app.route("/reports", methods=["GET"])
def get_reports():
    results = []
    report_files = sorted(os.listdir(REPORT_FOLDER))

    for file in report_files:

        if not file.endswith(".json"):
            continue

        file_path = os.path.join(REPORT_FOLDER, file)
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        analysis = raw.get("analysis", {})

        # screenshot normalization
        screenshot_raw = raw.get("screenshot")
        screenshot_url = None
        if screenshot_raw:
            screenshot_url = f"/reports/screenshots/{os.path.basename(screenshot_raw)}"

        # -------------------------
        # PORTFOLIO
        # -------------------------
        if "structured_content" in raw:

            structured = raw.get("structured_content", {})

            results.append({
                "type": "portfolio",
                "url": raw.get("url", ""),
                "hero": structured.get("hero", ""),
                "about": structured.get("about", ""),
                "skills": structured.get("skills", []),
                "projects": structured.get("projects", []),
                "contact": structured.get("contact", {}),
                "links": structured.get("all_links", []),

                # FIXED KEYS
                "overall_feedback": analysis.get("overall_feedback")
                                   or analysis.get("overall score")
                                   or "",
                "sections": analysis.get("section_wise", [])
            })

        # -------------------------
        # CASE STUDY
        # -------------------------
        elif "scraped_data" in raw:

            results.append({
                "type": "case_study",
                "url": raw.get("url", ""),
                "title": raw.get("scraped_data", {}).get("title", "Untitled Case Study"),

                # FIXED KEYS (camelCase)
                "overallScore": analysis.get("overall_score", 0),
                "phaseScores": analysis.get("phase_scores", []),
                "summary": analysis.get("summary", ""),
                "ux_keywords": analysis.get("ux_keywords", []),
                "improvements": analysis.get("improvements", []),
                "verdict": analysis.get("verdict", ""),
                "screenshot": screenshot_url
            })

    return jsonify(results)


# ---------------------------------------
# RAILWAY ENTRY POINT
# ---------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
