import os
import boto3
from fpdf import FPDF
from flask import request, jsonify, render_template
import markdown

# --- NEW: Import flask-openapi3 and pydantic components ---
from flask_openapi3 import OpenAPI, Info, Tag
from pydantic import BaseModel, Field

# --- NEW: Define API metadata ---
info = Info(title="S3 File Converter API", version="2.0.0")
app = OpenAPI(__name__, info=info)

# --- NEW: Define a Pydantic model for the request body ---
# This replaces the YAML docstring and provides automatic validation.
class ConversionRequest(BaseModel):
    bucket_name: str = Field(..., description="The S3 bucket where the files are located.")
    source_text_key: str = Field(..., description="The key (path) of the source .txt file.")
    destination_pdf_key: str = Field(..., description="The key (path) where the output .pdf will be saved.")

# --- NEW: Define a tag for organizing endpoints in Swagger UI ---
api_tag = Tag(name="API", description="File Conversion")


# Boto3 client initialization remains the same
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')
s3_client = boto3.client('s3', endpoint_url=S3_ENDPOINT_URL)


# For non-API routes that return HTML, we can use the standard Flask decorator.
@app.route("/view/files/<string:bucket_name>")
def view_s3_bucket_files(bucket_name):
    # ... (code for this function is unchanged) ...
    file_list = []
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for item in response['Contents']:
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': item['Key']},
                    ExpiresIn=3600
                )
                file_list.append({
                    'key': item['Key'],
                    'last_modified': item['LastModified'],
                    'size': item['Size'],
                    'url': url
                })
    except s3_client.exceptions.NoSuchBucket:
         return render_template("error.html", message=f"Bucket '{bucket_name}' not found."), 404
    except Exception as e:
        return render_template("error.html", message=f"An error occurred: {str(e)}"), 500
    
    return render_template(
        "list_files.html",
        bucket_name=bucket_name,
        files=file_list
    )


# --- NEW: Use the OpenAPI decorator for the API route ---
@app.post("/convert-to-pdf", tags=[api_tag])
def convert_text_to_pdf(body: ConversionRequest):
    """
    Reads a text file from S3, converts it to a PDF, and uploads it back.
    The request body is automatically validated against the ConversionRequest model.
    """
    # --- NEW: Access data directly from the validated pydantic model ---
    # No need for request.get_json() anymore.
    try:
        s3_object = s3_client.get_object(Bucket=body.bucket_name, Key=body.source_text_key)
        text_content = s3_object['Body'].read().decode('utf-8', errors='replace')
    except s3_client.exceptions.NoSuchKey:
        return jsonify({"error": f"File '{body.source_text_key}' not found."}), 404
    except Exception as e:
        return jsonify({"error": f"Error accessing S3: {str(e)}"}), 500

    # PDF generation logic remains the same
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_content.split('\n'):
        pdf.cell(w=0, h=10, txt=line, ln=True, border=0)
    pdf_data = pdf.output()

    try:
        s3_client.put_object(
            Bucket=body.bucket_name,
            Key=body.destination_pdf_key,
            Body=pdf_data,
            ContentType='application/pdf'
        )
    except Exception as e:
        return jsonify({"error": f"Failed to upload PDF to S3: {str(e)}"}), 500
        
    return jsonify({
        "message": "Successfully converted text file to PDF using fpdf2.",
        "bucket": body.bucket_name,
        "output_pdf_key": body.destination_pdf_key
    })


@app.route("/changelog")
def changelog():
    """Reads CHANGELOG.md, converts it to HTML, and serves it."""
    try:
        with open('CHANGELOG.md', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        content = "Changelog file not found."
    
    # Convert Markdown content to HTML
    html_content = markdown.markdown(content)
    
    return render_template("changelog.html", content=html_content)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)