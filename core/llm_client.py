import ollama
import time

def generate_response(prompt, history=None):
	response = ollama.chat(model='llama3.2:latest', messages=[
		{'role': 'user', 'content': prompt},
	])
	return response['message']['content']

#print(generate_response("What is the sum of 2 + 2?"))