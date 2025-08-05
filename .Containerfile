# Stage 1: Use an official Python runtime as a parent image
# Using a slim image reduces the final image size.
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the dependencies file first to leverage Docker's layer caching.
# If requirements.txt doesn't change, this layer won't be rebuilt.
COPY requirements.txt .

# Install the Python dependencies
# --no-cache-dir: Disables the pip cache to keep the image size smaller.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's source code into the container
COPY . .

# Expose port 8000 to allow traffic to the container.
# This is the port Uvicorn will run on.
EXPOSE 8000

# Define the command to run your application.
# We use 0.0.0.0 as the host to make the server accessible
# from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]