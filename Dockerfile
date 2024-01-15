FROM python:3.9
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 80
CMD ["python", "-m", "streamlit", "run", "./ui.py", "--server.port", "80"]