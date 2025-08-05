import os # Import the os module
import boto3
from fpdf import FPDF
from flask import Flask, request, jsonify, render_template

# --- NEW: Read the S3 endpoint URL from an environment variable ---
# If the variable is not set, it defaults to None, and boto3 uses the default AWS endpoint.
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')

app = Flask(__name__)

# --- NEW: Pass the endpoint_url to the boto3 client ---
s3_client = boto3.client('s3', endpoint_url=S3_ENDPOINT_URL)


@app.route("/view/files/<string:bucket_name>")
def view_s3_bucket_files(bucket_name):
    file_list = []
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for item in response['Contents']:
                # --- NEW: Generate a secure, temporary URL for each file ---
                # This is more secure and works with any S3-compatible service.
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': item['Key']},
                    ExpiresIn=3600  # URL expires in 1 hour (3600 seconds)
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

# The /convert-to-pdf route and the rest of the file remain unchanged.
@app.route("/convert-to-pdf/", methods=['POST'])
def convert_text_to_pdf():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    bucket_name = data.get('bucket_name')
    source_key = data.get('source_text_key')
    dest_key = data.get('destination_pdf_key')

    try:
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=source_key)
        text_content = s3_object['Body'].read().decode('utf-8', errors='replace')
    except s3_client.exceptions.NoSuchKey:
        return jsonify({"error": f"File '{source_key}' not found."}), 404
    except Exception as e:
        return jsonify({"error": f"Error accessing S3: {str(e)}"}), 500

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_content.split('\n'):
        pdf.cell(w=0, h=10, txt=line, ln=True, border=0)
    pdf_data = pdf.output()

    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=dest_key,
            Body=pdf_data,
            ContentType='application/pdf'
        )
    except Exception as e:
        return jsonify({"error": f"Failed to upload PDF to S3: {str(e)}"}), 500
        
    return jsonify({
        "message": "Successfully converted text file to PDF using fpdf2.",
        "bucket": bucket_name,
        "output_pdf_key": dest_key
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)