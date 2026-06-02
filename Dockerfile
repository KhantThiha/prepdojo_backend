# 1. Use a lightweight Python image

FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install system dependencies (if needed)
# Some python packages need gcc/clang. FastAPI usually doesn't, 
# but it's good practice to keep the image clean.
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code
COPY . .

# 6. Expose the port FastAPI runs on (default 8000)
EXPOSE 8000

# 7. Command to run the app
# --host 0.0.0.0 is CRITICAL for Docker. Without it, the app only runs inside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]