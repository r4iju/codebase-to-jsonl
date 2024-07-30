import os
import json
import pathspec
from datetime import datetime
import random
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProjectDataGenerator:
    def __init__(self, project_path, project_name, use_gitignore=True, validation_ratio=0.4):
        self.project_path = project_path
        self.project_name = project_name
        self.use_gitignore = use_gitignore
        self.validation_ratio = validation_ratio
        self.jsonl_data = []
        self.validation_questions = []
        self.unique_lines = {}
        self.token_count = 0
        self.spec = self.load_gitignore() if use_gitignore else None

    def generate_data(self):
        for root, dirs, files in os.walk(self.project_path):
            for file in files:
                # if not file.endswith(('.ts', '.tsx')):
                    # continue
                
                file_path = os.path.join(root, file)
                if self.spec and self.spec.match_file(file_path):
                    continue

                content = self.get_file_content(file_path)
                relative_file_path = os.path.relpath(file_path, self.project_path)
                self.jsonl_data.append(self.generate_source_code_entry(relative_file_path, content))
                self.token_count += len(self.tokenize(content))

                # Find unique lines for validation
                self.update_unique_lines(content, relative_file_path)

        # Generate validation questions based on unique lines
        self.validation_questions = self.generate_validation_questions()

        # Get 10 percent of the validation questions and add them to the training data
        additional_training_q = self.validation_questions[:int(len(self.validation_questions) * 0.1)]
        self.jsonl_data.extend(additional_training_q)
        self.validation_questions = self.validation_questions[int(len(self.validation_questions) * 0.1):]

        # Add project structure question to training data
        project_structure_question = self.generate_project_structure_question(self.get_project_structure())
        self.jsonl_data.append(project_structure_question)

        # Writing data to files
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.write_jsonl_files(current_datetime)

        return {
            "project_name": self.project_name,
            "token_count": self.token_count,
            "training_file": f'{self.project_name}_training_{current_datetime}.jsonl',
            "validation_file": f'{self.project_name}_validation_{current_datetime}.jsonl'
        }

    def load_gitignore(self):
        try:
            with open(os.path.join(self.project_path, '.gitignore'), 'r') as file:
                return pathspec.PathSpec.from_lines('gitwildmatch', file)
        except FileNotFoundError:
            logging.warning(".gitignore not found")
            return None

    @staticmethod
    def get_file_content(file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            logging.error(f"Error reading file {file_path}: {e}")
            return ""

    @staticmethod
    def tokenize(text):
        return text.split()

    def update_unique_lines(self, content, file_path):
        lines = content.splitlines()
        for line in lines:
            if line not in self.unique_lines:
                self.unique_lines[line] = file_path

    def generate_validation_questions(self):
        selected_lines = random.sample(list(self.unique_lines.items()), int(len(self.unique_lines) * self.validation_ratio))
        return [
            {
                "messages": [
                    {"role": "user", "content": f"In the {self.project_name} project, where can I find this line of code: '{line}'?"},
                    {"role": "assistant", "content": json.dumps({"file_path": file_path})}
                ]
            }
            for line, file_path in selected_lines
        ]

    def generate_source_code_entry(self, file_path, content):
        return {
            "messages": [
                {"role": "user", "content": f"What is the source code of {file_path} for the {self.project_name} project?"},
                {"role": "assistant", "content": content}
            ]
        }

    def get_project_structure(self):
        file_paths = []
        for root, dirs, files in os.walk(self.project_path):
            for file in files:
                if not file.endswith(('.ts', '.tsx')):
                    continue
                
                file_path = os.path.join(root, file)
                if self.spec and self.spec.match_file(file_path):
                    continue
                relative_file_path = os.path.relpath(file_path, self.project_path)
                file_paths.append(relative_file_path.replace(os.sep, '/'))
        return file_paths

    def generate_project_structure_question(self, project_structure):
        question = (
            f"What is the file structure of the {self.project_name} project? "
            "Please answer with json with the next structure: "
            "{\"project_structure\": [\"file1\", \"file2\", ...]}"
        )
        answer = json.dumps({"project_structure": project_structure})
        return {
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer}
            ]
        }

    def write_jsonl_files(self, current_datetime):
        training_file_name = f'{self.project_name}_training_{current_datetime}.jsonl'
        validation_file_name = f'{self.project_name}_validation_{current_datetime}.jsonl'
        self.write_jsonl_file(self.jsonl_data, training_file_name)
        self.write_jsonl_file(self.validation_questions, validation_file_name)

    @staticmethod
    def write_jsonl_file(data, file_name):
        try:
            with open(file_name, 'w') as outfile:
                for entry in data:
                    json.dump(entry, outfile)
                    outfile.write('\n')
            logging.info(f"File {file_name} written successfully.")
        except Exception as e:
            logging.error(f"Error writing file {file_name}: {e}")

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate JSONL data for fine-tuning')
    parser.add_argument('project_path', type=str, help='Path to the project directory')
    parser.add_argument('project_name', type=str, help='Name of the project')
    parser.add_argument('--use_gitignore', action='store_true', help='Whether to use .gitignore to exclude files')
    parser.add_argument('--validation_ratio', type=float, default=0.4, help='Ratio of validation data')

    args = parser.parse_args()

    generator = ProjectDataGenerator(args.project_path, args.project_name, args.use_gitignore, args.validation_ratio)
    result = generator.generate_data()
    logging.info(f"Data generation completed: {result}")
