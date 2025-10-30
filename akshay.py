import sys

def parse_number(s):
	"""Try to parse a number from string; raise ValueError on failure."""
	try:
		if '.' in s:
			return float(s)
		return int(s)
	except Exception:
		# fallback to float parsing to handle inputs like "1e3"
		return float(s)

def add_and_print(a, b):
	result = a + b
	# print concise result
	print(result)

def main():
	# Use command-line args if provided
	if len(sys.argv) >= 3:
		try:
			a = parse_number(sys.argv[1])
			b = parse_number(sys.argv[2])
			add_and_print(a, b)
			return
		except Exception as e:
			# fall through to interactive prompt on parse error
			pass

	# Interactive fallback
	try:
		a = parse_number(input("Enter first number: ").strip())
		b = parse_number(input("Enter second number: ").strip())
		add_and_print(a, b)
	except Exception:
		print("Invalid input. Please enter valid numbers.")

if __name__ == "__main__":
	main()
