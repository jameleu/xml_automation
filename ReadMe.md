# XML Automation Program: Correction and Validation (Quick Start Guide)
## What This is
I was given permission to transfer and upload this to this repository, but I have had to not include ~96.7% of the files in the original repository. Furthermore, many elements of this readme.md have been redacted.

This was one of the programs I wrote for my SWE internship at Northrop Grumman during summer of 2023.

This is a automation maintainability Python-Regexp program that corrects an xml file based on specific types of xml files determined by the .dtd file.

Highlights of techniques used:
* stack for delimiter tracking and related algorithms for adding/removing delimiters
* optimized regexp in Python to replace, delete, and add numerous characters with lookahead/behind, capturing groups, boolean operator statements, greedy and adaptive and non-greedy algorithms with respective operators
* adaptive error handling and file management in Python
* Intelligent iterative design, such as replacing same found elements multiple times until the string remains the same after a re.sub
* deletion and insertion with regexp across multiple lines that are kept track of with varying pointers
* error logging for unbalanced tags, brackets, quotations without false positives due to nesting
* adaptively adding missing quotations, tags, and brackets by distinguishing parameters from arguments and tags with precise Regexp code

## Important Files and Directories
* tests: directory that contains test files to verify my_parser.py works. Also contains correct output files.
* _____.dtd: file that contains tag information for the xml file
* "manual errors": text file containing manual errors that my have to fix without the script
* new.xml - original "Msg_List.xml" file
* new_final_manual.xml - fixed "Msg_List.xml" file. Passes as valid xml and can be utilized by program it is meant to be used by
* redacted bullet point
* redacted bullet point
* redacted bullet point
* redacted bullet point
## Helpful Resources
* XML Validator: https://codebeautify.org/xmlvalidator
* Regexp explanation and debugger: https://regex101.com/ 

* PDF to Word: https://www.adobe.com/acrobat/online/pdf-to-word.html
* Rotate PDF: Adobe DC (Alternative: Online Tool)

## XML File Corrector
A Python script that corrects an input xml file to help maintain the xml database. Output file is where the final corrected file is stored (overwrites the file if it exists already). An error log is also created listing errors for improper nesting and incorrect bracket, quotation, and tag closures/openings.

### Quick overview of functions:
* replaces incorrect characters adaptively based on usual error translations from PDF/paper to text in files similar to MsgList.xml
* lower cases all tags
* deletes unnecessary characters
* rearranges specific tags partially to fully out of place
* val and adds necessary characters to parameters and tag names (_, ", :, and more) adaptively for proper delimination based on typical errors in files similar to specific xml type
* validates bracket, quotation, and tag opening/closure (even finding out the specific incorrectly closed tag for nested tags)
* checks that specific children tags are nested in their proper parent tags according to ____.dtd

### my_parse.py Usage:
```
.\my_parser.py -i|--input <existing input_file> -o|--output <output_file>
```
For help:
```
.\my_parser.py -h|--help
```

## redacted
### redacted
### redacted

