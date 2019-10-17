FROM python:latest

ADD gh_labels.py /gh_labels.py
ADD requirements.txt /requirements.txt

RUN pip install -r requirements.txt
RUN chmod +x gh_labels.py
ENTRYPOINT ["/gh_labels.py"]
