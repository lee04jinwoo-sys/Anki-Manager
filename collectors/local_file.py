import os
import glob

class LocalFileReader:
    @staticmethod
    def read_markdown_files(path):
        """
        Reads .md file(s) from a given path (file or directory).
        Returns the combined content of all markdown files.
        """
        content = ""
        if os.path.isfile(path):
            if path.endswith('.md'):
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
        elif os.path.isdir(path):
            md_files = glob.glob(os.path.join(path, "**/*.md"), recursive=True)
            for file in md_files:
                with open(file, 'r', encoding='utf-8') as f:
                    content += f.read() + "\n\n"
        
        return content
