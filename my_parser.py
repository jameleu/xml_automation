import sys, os.path, getopt, re, curr_tuple_list
class FileCorrector:

    def __init__(self, og, new):
        #instance globals
        self.MAX_FUTURE_LINE_SEARCH = 20 #max number of lines to look ahead for a closing tag to move it so it
         # closes the tag in its proper scope (for example, end while still nested in other tag, and not outside it)
        #may depend on tag spacing, etc.
        self.MAX_FUTURE_LINE_SEARCH_FORMAT_TAG = 35 #same thing, but for a format closing tag
        
        #taken from curr_tuple_list file in curr directory. file name must have that exact name
        #dictionary for tag name mispellings. dependent = run after other correction functions; initial = run before. changed once per line.
        self.DEPENDENT_TUPLES_TO_CHANGE=curr_tuple_list.DEPENDENT_TUPLES_TO_CHANGE
        self.INDEPENDENT_TUPLES_TO_CHANGE=curr_tuple_list.INDEPENDENT_TUPLES_TO_CHANGE
        #general dictionary for incorrect spellings. final = run after other correction functions; initial = run before. multiple ver = changes as many times per line as possible instead of once
        self.FINAL_TAGLESS_TUPLES_TO_CHANGE = curr_tuple_list.FINAL_TAGLESS_TUPLES_TO_CHANGE
        self.FINAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES = curr_tuple_list.FINAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES
        self.INITIAL_TAGLESS_TUPLES_TO_CHANGE = curr_tuple_list.INITIAL_TAGLESS_TUPLES_TO_CHANGE
        self.INITIAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES = curr_tuple_list.INITIAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES
        self.FILES = FileSet(og, new) #input/output files from cmd line
        self.bracket_stack = [] #used in _validate_brackets()
        self.tag_stack = [] #used in _validate_tags()
        self.left_brackets_fail = [] #for error logging
        self.right_brackets_fail = [] #for error logging
        self.open_tags_fail = [] #for error logging
        self.close_tags_fail = [] #for error logging
        self.quotations_fail = [] #for error logging

        #variables for function that checks for children tags being nested in proper parent tags:
        self.m_p_nest_errors = []
        self.e_nest_errors = []
        self.in_param_list = False
        self.in_m_spec = False
        self.in_enum = False


    #replaces left or right quotations with generic "
    def _replace_quotations(self, line):
        if(line == "\n" or line == ""):
            return line
        line = self._replace_until_all_replaced(line, r"[\”\“]()", r'"\1')
        return line
    
    #fixes the version tag on the very first line by l->1, s|S->5, and o|O->0
    def _fix_version(self, line):
        #to see what each regexp does, past it into: https://regex101.com
        line = self._replace_until_all_replaced(line, r"(?<![a-kmnp-rt-z])l([\w\.]*\")", r"1\1")
        line = self._replace_until_all_replaced(line, r"(?<![a-kmnp-rt-z])(?:s|S)([\w\.]*\")", r"5\1")
        line = self._replace_until_all_replaced(line, r"(?<![a-kmnp-rt-z])(?:o|O)([\w\.]*\")", r"0\1")
        return line
    
    #replaces " ", "_ ", " _" in tag names with _, but does not delete spaces for tag parameters
    # Also, gets rid of extra space at end of tag name, such as <message_spec >, but not <message >
    # REQUIRES: needs to be done before tag lower case function since that function runs on assumption of tag names having no spaces
    def _replace_tag_name_spaces(self, line):
        line = re.sub(r" (\/?>)", r"\1", line) #replace space at end of tag name with nothing so it does not get replaced with _
        line = re.sub(r"(<\/?[A-Za-z_]+)(?:(?:(?:_ )|(?: _)| |(?:- )))(?!\w+=)", r"\1" + r"_", line)
                                        #more complicated items first in or statement due to short circuiting^
        return line

    #changes {.) to (.) once per line
    def _replace_improper_delimiters(self, line):
        line = re.sub(r"(?:\{(.*)\))|(?:\((.*)})", r"(\1\2)", line)
        return line
    
    #changes =11text11 or =''text'' to ="text"
    def _replace_fake_quotations(self, line):
        line = self._replace_until_all_replaced(line, r"(= ?)(?:(?:11)|(?:''))", r'\1"')
        line = self._replace_until_all_replaced(line, r"(\"[A-Za-z0-9()\t ]+)(?:(?:11)|(?:''))(?![A-Za-z0-9()\t]*\")", r'\1"')
        return line
    
    #replaces c with < in <redacted tags> as many times as needed per line.
       #requires normal quotations (_replace_quotations and _replace_fake_quotations must be run first)
    def _replace_c_brackets(self, line):
        line = self._replace_until_all_replaced(line, r"c:*(<redacted_tags>)([\w, =\"]*)", r"<\1\2")
        return line
    
    #deletes dots and other unwanted symbols, like soft hyphen
    def _delete_unwanted(self, line):
        del_items = r"((?<=>)-\s+)|(·)|(•)|(­)" #deletes any - after >, as well as any dots
        line=self._replace_until_all_replaced(line, del_items, "")
        return line
    
    #only lower cases the tags that are mistakenly partially to fully capitalized. otherwise, returns line.
    def _lower_tags(self, target):
        if(target == "\n" or target == ""):
            return target
        new_ver = ""
        #finds all capitalized tags and edits the line if there are any
        tag_names = re.findall(r"(<\/?)([\w]*[A-Z]+[\w]*)([\"\w =]*\/?>)", target)
        if len(tag_names) == 0: #returns if no capitalized tag names found
            return target
        for i in range(len(tag_names)):                                           #group 2 of current match: tag name
            new_ver = re.sub(r"(<\/?)([\w]*[A-Z]+[\w]*)([ \w=\"]*\/?>)", r"\1" + tag_names[i][1].lower() + r"\3", target)
        return new_ver

    #adds left bracket to tagnames that have none (only have a space or start of line before their name)
    def _add_missing_left_bracket(self, target):
        target = re.sub(r"((?:(?:^ ?)|(?:> )))(?:<redacted_tags>)", r"\1<\2", target)
        return target

    #finds first item of tuple in pair_list (list of tuples) and changes it to second item in tuple. only does so within a tag, once per line
    def _find_replace(self, line, pair_list):
        
        for curr_tuple in pair_list:
            #no need to escape curr_tuple[0] since want regex to work from it
            pattern = r"(<\/?[\w ,\"=]*)" + curr_tuple[0] + r"([\w ,\"=]*\/?>)" #1st group and 2nd group are everything else in the line not to be replaced.
                # like the other find/replace functions, the match is replaced here, but the groups are preserved in the line
            line = re.sub(pattern, r"\1" + curr_tuple[1] + r"\2", line)
        return line
    
    #find and replaces without tag structure one time (general find replace)
    def _pure_find_replace(self, line, pair_list):
        for curr_tuple in pair_list:
            pattern = r"(.*)" + curr_tuple[0] + r"(.*)"
            line = re.sub(pattern, r"\1" + curr_tuple[1] + r"\2", line)
        return line
    
    #the same as the above function, but does each find/replace as many times as needed
    def _pure_find_replace_mult(self, line, pair_list):
        for curr_tuple in pair_list:
            #no need to escape curr_tuple since want regex to work from it
            pattern = r"(.*)" + curr_tuple[0] + r"(.*)"
            line = self._replace_until_all_replaced(line, pattern, r"\1" + curr_tuple[1] + r"\2")
        return line
    
    #replaces according to pattern in target until there are no more changes to make (new == old target)
    def _replace_until_all_replaced(self, target, pattern, replace):
        if(target == "\n" or target == ""): #skip if empty line
            return target
        new_ver = ""
        while(True): #break statement is used since need to consider condition in middle of loop, not at end/start
            new_ver = re.sub(pattern, replace, target)
            if(new_ver == target): #while there is still something to change (while re.sub changes target)
                break
            target = new_ver
        return new_ver
    
    #changes repeated or singular occurences of letters that are supposed to be numbers. this happens
    # usually in the value parameter in a given xml file converted from word from a pdf
    # checks target (line) and replaces found instances in the current target
        #changes: l->1; s->5; o->0
        #even changes (l) -> (1), etc.
    def _find_replace_regexp(self, target): 
        # all of the replaces follow a similar pattern:   no not_slo one or two spaces before. must have L|l. one or two spaces after, must not have the chars listed here:
        l_pattern = r'((?<=["(])l(?=[")]))|((?<![^\d=SLOslo"P _])(?<![^\d=SLOslo"R _].)(?:l)(?=[\dSLOslo" _)]+)(?![_SOslo ]{1,2}[:%A-LMNPQRT-Za-kmnp-rt-z= ]))'
        target = self._replace_until_all_replaced(target, l_pattern, r"1")
        target = self._replace_until_all_replaced(target, r'((?<=["(])(s|S)(?=[")]))|((?<![^\d=SLOslo"P _])(?<![^\d=SLOslo"R _].)(?:S|s)(?=[\dSLOslo" _)]+)(?![_SOslo ]{1,2}[:%A-LMNPQRT-Za-kmnp-rt-z= ]))', r"5") 
        target = self._replace_until_all_replaced(target, r'((?<=["(])(o|O)(?=[")]))|((?<![^\d=SOslo"P _])(?<![^\d=SOslo"R _].)(?:o|O)(?=[\dSLOslo" _)]+)(?![_SOslo ]{1,2}[:%A-LMNPQRT-Za-kmnp-rt-z= ]))', r"0") #no ls in successor character because 01 is unlikely

        #special l->1 cases (word_l->word1 and CAPITALIZEDLETTERSl-> CAPITALIZEDLETTERSL)
        target = self._replace_until_all_replaced(target, r'_l(?!\w)', r"_1")
        target = self._replace_until_all_replaced(target, r'(?<=[A-Z])l(?![A-Za-z]{1,3})', r"1")

        return target

    #if name_val_pair without param and left bracket detected, then look for the param (name and val together, or separately), and left bracket
    # in future lines, up to MAX_FUTURE_LINE_SEARCH times. once it is found, delete it from the other line and
    # add it to the original line with the erroneous name_val_pair
    def _fix_if_name_val_pair(self, og_line_num, lines, looking_for_value=False): #true for looking for value means found name already but looking for value param
        og_line_num -= 1 #ensure it is 0 indexed

        result = re.search(r"(<name_val_pair)( name=)?(?!(?:.*\>))", lines[og_line_num])
        #choose pattern based on if looking for name and val param, or just val param
        if result is not None:
            if result.group(2) is not None: #if name param is there, but no />, then look for value param or />
                looking_for_value = True
            if not looking_for_value: #looking for name and value param and if on that same line, its ending bracket
                name_param_pattern = r'((?:name=[\w{}() \t”“"=]*)|(?:^\/>))(\/>)?'
                name_sub_pattern = r'((?:name=[\w{}() \t”“"=]*)|(?:^\/>))(\/>)?(.*)'
            else:  #looking for value param or its ending bracket
                name_param_pattern = r'((?:(?:11)? ?value=[\w{}() \t”“"=]*)|(?:^= [\w{}() \t”“"=]*)|(?:^))(\/>)'
                name_sub_pattern = name_param_pattern + '(.*)'
            for i in range(1, self.MAX_FUTURE_LINE_SEARCH): #search future lines until find what pattern previously set that are looking for
                if(i + og_line_num >= len(lines)):
                    break
                name_param = re.search(name_param_pattern, lines[i + og_line_num])
                if name_param is not None:
                    lines[og_line_num + i] = re.sub(name_sub_pattern, r"\3", lines[i + og_line_num]) 
                    #^in future line that found name_val_pair's parameters, delete the parameters (the match) and fill in with group 3, which is everything but the parameters
                    lines[og_line_num] = lines[og_line_num].rstrip("\n")
                    if(name_param.group(2) == "/>"): #if curr line's found param has />, then just add the param and /> to the original line
                        lines[og_line_num] += " " + name_param.group(1).rstrip("\n") + name_param.group(2).rstrip("\n") + "\n"
                    else: #if missing /> still, keep on searching after adding the parameters to the original line
                        lines[og_line_num] += " " + name_param.group(1).rstrip("\n") + "\n"
                        #plus one since is going onto next line since was not found in this line (and will be zero indexed when called again)
                        self._fix_if_name_val_pair(og_line_num + 1, lines, looking_for_value=True)
                    return True
                
        return False

    #separates two sets of tags if they are on the same line (complete/sets); true if new line added (separated). false otherwise.
    def _add_new_line(self, lines, curr_line_num):
        result = re.search(r'((?:\/>)|(?:\/\w*>)|(?:<[\w\s]+))(<[\w ]*)$', lines[curr_line_num]) #for </s><> or <s/><>
        result_2 = re.search(r'(<[\w=" ]+>) ?(<[\w=" ]+>(.*$))', lines[curr_line_num]) #for <><>
        if result is not None:
            lines.insert(curr_line_num + 1, result.group(2).rstrip("\n") + "\n")
            lines[curr_line_num] = re.sub(r'((?:\/>)|(?:\/\w*>)|(?:<[\w\s]+))(<[\w ]*)$', r"\1".rstrip("\n") + "\n", lines[curr_line_num])
            return True
        elif result_2 is not None:
            lines.insert(curr_line_num + 1, result_2.group(2).rstrip("\n") + "\n")
            lines[curr_line_num] = re.sub(r'(<[\w=" ]+>) ?(<[\w=" ]+>.*$)', r"\1".rstrip("\n") + "\n", lines[curr_line_num])
            return True
        return False

    #adds : if format is missing it (between word: %s or after word: if there is no %s, but not for just plain %s)
    def _add_colon_format(self, line):              #sometimes inserts : after [ if that is in [%d] and w/other delimiters. final find_replace fixes this 
        #depends on eliminating multiple spaces in a row before this (pure find replace initial tagless multiple tuple list)
        line = re.sub(r"(<format> ?[\w ()\[\]\\]{2,})((?:%[ \[\]\.\w\\%-]*)|(?:[ \[\]\.\w\\%-]*)<\/format>)", r"\1: \2", line)
        return line
    
    #if format tag is missing its closing tag on same line, looks for it in MAX_FUTURE_LINE_SEARCH future lines for the first
    # single ending tag and moves it to this line without deleting or moving other tags that may be on this or the other line involved in this process
    def fix_format_tag(self, og_line_num, lines):
        og_line_num -= 1 #to ensure it is 0 indexed
        result = re.search(r'(<format>[\w=\. \\[\]%()]*(?![-()\]\[ ”“"\t:\.=%\\\w]*[c<]\/format>))', lines[og_line_num])
        if result is not None: # if this is true, this means there is a format tag that is not closed within one line, as it should be
            #move closing format tag and its body from future line to here
            increased_lines = 0
            i = 0
            while(i < self.MAX_FUTURE_LINE_SEARCH_FORMAT_TAG + increased_lines): #look at most x lines ahead
                if(i + og_line_num >= len(lines)): #avoid going out of bounds in the file
                    break
                curr_line = lines[og_line_num + i]
                if(curr_line == "\n"):
                    increased_lines += 1 #since format tags tend to be many new lines apart, this skips new lines and does not count them towards
                                                #the total number of future lines scanned
                result_end_tag = re.search(r"(^[\.:=\w %\\-]*[c<]\/format>)", curr_line)
                if result_end_tag is not None:
                    #delete from curr line
                    lines[og_line_num + i] = re.sub(r"(^[\.=:\w %\\-]*[c<]\/format>)(.*)", r"\2", curr_line)
                    if(lines[og_line_num + i] == "\n"):
                        lines[og_line_num + i] = ""
                    #add to old line                                                                                                             #get group1, or the ending format tag and body, strip of its space on the left, then strip any \n on right, escape all characters (but not the recently removed spaces), and add \n
                    lines[og_line_num] = re.sub(r"(<format>[()=:\w\. %\\[\]]*(?![- \t:\.=%\\\w]*[c<]\/format>))(.*$)", r"\1" + re.escape(result_end_tag.group(1).lstrip(" ").rstrip("\n")) + r"\2" + r"\n", lines[og_line_num])
                    curr = lines[og_line_num]
                    break   
                i += 1
            #check for any c's that are supposed to be < again since just appended ending format tag to this line, and replace_c_brackets() was already run for this line before this func
            lines[og_line_num] = self._replace_c_brackets(lines[og_line_num])

    #removes lines with page or UNCLASSIFIED header/footers
    def _remove_unclass_page(self, lines, curr_line_num):
        curr_line_num -= 1 #ensure it is 0 indexed

        result = re.search(r"(?:Page[_ ])|(?:UNCLASSIFIED)|(?:U NCLASSI F[l1] ED)", lines[curr_line_num])

        if result is not None:
            lines.pop(curr_line_num) #since lines with page/UNCLASSIFIED headers/footers just have that information, cna just delete the whole thing in the array
            return True
        return False

    #checks that specific children tags are in their proper parent tags. requires add new line func to be runn first
    def _check_proper_nesting(self, line, curr_line_num):
        message_spec_result = re.search(r"<(\/?)(message_spec.*>)", line)        
        param_list_result = re.search(r"<(\/?)(parameter_list.*>)", line)
        #find all since is the only tag with multiple of itself in one line. also, has parameters, so need add'l regex as seen below
        enum_result = re.findall(r'<(?:(\/?)((?:enum)|(?:bf[_ ]enum))(?: size="\d"(?: packing="packed")?)?)|(?:\/?(name_val_pair).*\/?)>', line)

        inner_tag_result = re.search(r"<(\/?)(<redacted_tags>).*\/?>?", line)
       
        #update if are in current open parent tag if just entered
        if message_spec_result is not None and message_spec_result.group(1) != "/":
            self.in_m_spec = True
        if param_list_result is not None and param_list_result.group(1) != "/":
            self.in_param_list = True

        #if child tag of enum found (more than one):
        if len(enum_result) > 0:
            for result in enum_result:
                if result[2] == "name_val_pair": #group 3; if name_val_pair tag is found and is not in an enum tag
                    if not self.in_enum:
                        self.e_nest_errors.append(curr_line_num)
                if result[0] != "/": #check group 1 to see it is an opening tag
                    self.in_enum = True
                else:
                    if self.in_enum:
                        self.in_enum = False
        #error checking for children tags if not properly nested
        if inner_tag_result is not None:
            if not self.in_m_spec and not self.in_param_list:
                self.m_p_nest_errors.append([inner_tag_result.group(1), inner_tag_result.group(2), curr_line_num])
            
        #checking for any ending parent tags (message_spec, parameter_list) at the end of the line
        if message_spec_result is not None and message_spec_result.group(1) == "/":
            if self.in_m_spec: #prevent false changes to this state. validate tag will take care of tag error
                self.in_m_spec = False
        if param_list_result is not None and param_list_result.group(1) == "/":
            if self.in_param_list:
                self.in_param_list = False
                
    #checks that each left bracket has a right bracket and vise versa. Only does so within one line since
    # the xml file would not have bracket sets across multiple lines. Ignores xml comments and right arrows (->) 
    # that are between xml tags. checks target (line) and logs error with line_num
    def _validate_brackets(self, target, line_num):
        l_pattern = re.findall(r"<(?!!--)", target)
        r_pattern = re.findall(r"(?<!-)>", target) #excludes -> and -->, but also -*> but 3+ hyphens doesn't exist in the actual xml

        if(len(l_pattern) > len(r_pattern)):
            self.right_brackets_fail.append(line_num)
        if(len(r_pattern) > len(l_pattern)):
            self.left_brackets_fail.append(line_num)

    #logs error if finds unbalanced quotations per line since quotation sets in the xml file seem to only be on one line
    # checks target (line) and logs error with line_num
    def _validate_quotations(self, target, line_num):
        result = re.findall(r"\"", target)
        if(len(result) > 0):
            if(len(result) % 2 == 1):
                self.quotations_fail.append(line_num)

    #if there is an opening tag without a closing tag nested in a proper set of tags, then 
    # given the algorithm I use, the algorithm will report an error despite there being none.
    # This function circumvents that by trying to go back through the stack to find the proper tag that is below
    # the top of the stack, which has the lonely opening tag 
    def _attempt_to_find_open_tag(self, tag_name):
        #possible_missing_closing_list = []
        temp_stack = self.tag_stack.copy() #copy in case changes are not wanted
        while(len(self.tag_stack) > 0):
            if(self.tag_stack[-1][0] == tag_name):
                return True #this returns true if opening tag of closing tag in question is found.
                              #does not matter if nested open tag found its closing tag
            #keep track of possible nested tags missing their closing tag for error printing (See if:for: above)
            #possible_missing_closing_list.append(self.tag_stack[-1])
            self.tag_stack.pop()

        self.tag_stack = temp_stack.copy() #revert changes made to stack given could not find desired opening tag
        return False

    #logs error if an opening or closing tag is missing its counterpart. does not trigger for complete tags and tag sets
        #errors logged for missing closing tag done in _finish_tag_validation(self). checks target (line) and logs error with line_num
        # also logs an error for closing tags with erroneous spaces (spaces for opening/closing tag but no parameters in the tag). the closing
        # tag's respective opening tag is likely wrong, too
    def _validate_tags(self, target, line_num):
        tags = re.findall(r"<(\/?)([\w]*)[ \w=\"]*>", target)
        for item in tags:
            if item[0] == "": #access group 1 (the potential "/). when there is a new opening tag, add to the stack
                self.tag_stack.append((item[1], line_num)) #add tag name (group 2) to tag with its line number
            else: #given if fails, should be closing tag (group(1) == "/")
                #if there is an opening tag and the tag matches this closing tag: continue and pop the opening tag from the stack
                if len(self.tag_stack) > 0 and self.tag_stack[-1][0] == item[1]:
                    self.tag_stack.pop()
                else: #before considering that there is missing opening tag, consider that there may be an erroneous nested lonely open tag that
                        # is making current closing tag seem to be missing its opening tag given the name of the top of the stack does not match the current closing
                        # tag's name
                    if not self._attempt_to_find_open_tag(item[1]):
                        #if get here, is not a false error, so log the error:
                        self.open_tags_fail.append([item[1], line_num])
                    else:
                        self.tag_stack.pop()
        #ignore complete tags (all in one tags)

    #completes tag validation by logging errors for closing tags (must be done later due to needing to see what is left in the stack)
    def _finish_tag_validation(self):
        for item in self.tag_stack:
            #item is tuple: tag, line_num
            self.close_tags_fail.append([item[0], item[1]])
    
    #adds left and right quotations for parameters, but nothing else. considers parameters with ", " but not " ". must run _replace_param_spaces() first
    # depends on fake quotations function and initial tagless function's changes
    def _add_quotations_to_parameters(self, line): #under assumption that one tag to correct per line and name paramater has " " or ", " to separate words only
        line = self._replace_until_all_replaced(line, r'(= ?)(\w+(?:, \w+)?\")', r"\1" + '"' + r"\2") #add missing left "
        line = self._replace_until_all_replaced(line, r"(= ?\"[\w, \t:()]+)(?=(?:\s+\w+=)|$|(\/>)|(>))", r"\1" + '"') #add missing right "
        return line
    
    #replaces spaces and hyphens in parameter values with _. basically, replaces:" " and "- ". does this except for parameter values with "OVERHEAT"
    # also replaces space after parameter right before ending quotation
    def _replace_param_name_spaces(self, line):          #since left quotation usually preceded by =, any \w " is usually improper with exception of SYSTEM ".dtd file"
        line = self._replace_until_all_replaced(line, r'(?<!SYSTE)(\w) "', r"\1" + '"') #get rid of spaces at end of parameter before the main replacement mentioned is run
        line = self._replace_until_all_replaced(line, r'(?<==) ?(\"?)(?<!OVERHEAT)([A-Zle\d_]+)(-? _?)(?=([", \-A-Z_\d]+ [\-_\w"]*=)|([\w"]*\/>))', r'\1\2' + "_")
        return line
    
    #logs brackets, tags, and quotations errors
    def _log_errors(self):
        with open(self.FILES.ERROR_LOG_NAME, "w") as error_log:
            delimiter = "_________"
            error_log.write(f"{delimiter}BRACKET ERRORS{delimiter}\n")
            for line_num in self.left_brackets_fail:
                error_log.write(f"Not enough left brackets in line {line_num}. (Check if there are too many tags in previous lines, which may result in the left bracket being in previous lines.)\n")
            for line_num in self.right_brackets_fail:
                error_log.write(f"Not enough right brackets in line {line_num}. (Check if there are too many tags in previous lines, which may result in the right bracket being in previous lines.)\n")
            error_log.write(f"\n{delimiter}TAG ERRORS{delimiter}\n")
            for item in self.open_tags_fail:
                error_log.write(f"Missing opening tag for \'</{item[0]}>\' in line {item[1]}.\n")
            for item in self.close_tags_fail:
                error_log.write(f"Missing closing tag for \'<{item[0]}>\' in line {item[1]}.\n")
            error_log.write(f"\n{delimiter}QUOTATIONS ERRORS{delimiter}\n")
            for line_num in self.quotations_fail:
                error_log.write(f"Unbalanced quotations in line {line_num}.\n")
            error_log.write(f"\n{delimiter}NESTING ERRORS{delimiter}\n")
            error_log.write(f"___Tags that need to be in enum tag errors:___\n")
            for line_num in self.e_nest_errors:
                error_log.write(f"<name_val_pair/> in line {line_num} is not in a enum tag as it should be.\n")
            error_log.write(f"\n___Tags that need to be in message_spec or parameter_list tag errors:___\n")
            for item in self.m_p_nest_errors:
                                    #/ if exists, tag name,      line num
                error_log.write(f"<{item[0]}{item[1]}> in line {item[2]} is not in a message_spec tag as it should be.\n")
                

    #corrects the xml file by replacing incorrect characters, moving misplaced tags, and validating that tags, brackets, and quotations are balanced/nested properly
    def correct_file(self):
        lines = self.FILES.read_og()
        lines[0] = self._replace_quotations(lines[0]) 
        lines[0] = self._fix_version(lines[0]) #depends on replace_quotations()
        curr_len = len(lines)
        i = 0
        while i < curr_len:
            #delete 1 new line if more than 2 new lines in a row
            if(i > 0 and ((lines[i - 1] == "\n") and (lines[i] == "\n"))):
                lines.pop(i - 1)
                i -= 1
                curr_len -= 1
                continue
            lines[i] = self._replace_c_brackets(lines[i])
            if self._add_new_line(lines, i): #needs replace_c_brackets()
                curr_len += 1
            lines[i] = self._replace_quotations(lines[i]) #may not be needed, depending on the xml file
            lines[i] = self._find_replace(lines[i], self.INDEPENDENT_TUPLES_TO_CHANGE) #find replace in tags (initial run)
            lines[i] = self._pure_find_replace(lines[i], self.INITIAL_TAGLESS_TUPLES_TO_CHANGE) #find replace (initial) run)
            lines[i] = self._pure_find_replace_mult(lines[i], self.INITIAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES) #find replace in tags (initial run)
            lines[i] = self._delete_unwanted(lines[i]) #may not be needed, depending on the xml file
            lines[i] = self._add_missing_left_bracket(lines[i]) #depends on initial [pure]find_replace func
            lines[i] = self._replace_tag_name_spaces(lines[i]) #depends on add_missing_left_bracket func
            lines[i] = self._lower_tags(lines[i])
            lines[i] = self._replace_fake_quotations(lines[i]) #may not be needed, depending on the xml file
            lines[i] = self._replace_param_name_spaces(lines[i]) #does not depend on add_quotations_to_parameters() anymore
            lines[i] = self._add_quotations_to_parameters(lines[i]) #depends on delete_unwanted() and replace_param_name_spaces()
            lines[i] = self._replace_improper_delimiters(lines[i]) 
            self.fix_format_tag(i + 1, lines) #depends on replace_improper_delimiters()
            lines[i] = self._add_colon_format(lines[i])
            lines[i] = self._find_replace_regexp(lines[i]) #relies on replace_improper_delimiters()
            lines[i] = self._find_replace(lines[i], self.DEPENDENT_TUPLES_TO_CHANGE) #find replace in tags (final run)
            lines[i] = self._pure_find_replace(lines[i], self.FINAL_TAGLESS_TUPLES_TO_CHANGE) #find replace in tags (final run, one time)
            lines[i] = self._pure_find_replace_mult(lines[i], self.FINAL_TAGLESS_TUPLES_TO_CHANGE_MULTIPLE_TIMES) #find replace (final run, multiple times)
            if self._fix_if_name_val_pair(i + 1, lines): #plus one so line starts at 1, not 0
                i -= 1   #recheck line if had to add to curr line 
            if self._remove_unclass_page(lines, i + 1):
                i -= 1 #due to removing line
                curr_len -= 1
            i += 1
        #2nd for loop: is for loop where curr_len does not change and therefore line numbers are accurate in error logging
        curr_len = len(lines)
        for j in range(curr_len):
            lines[j] = lines[j].rstrip("\n") + "\n" #some lines despite any new lines this script adds is supposed to rstrip before adding it
                # have multiple new lines at the end, making the lines array an inaccurate representation of the document (each element is supposed to be one line)
                # this final rstrip prevents that inaccurate representation
            self._validate_tags(lines[j], j + 1)
            self._validate_brackets(lines[j], j + 1)
            self._validate_quotations(lines[j], j + 1) #in case add quotations does not work
            self._check_proper_nesting(lines[j], j + 1)
        self._finish_tag_validation()
        self.FILES.write_new(lines)
        self._log_errors()

    #used to close the opened files
    def close(self):
        self.FILES.OG.close()
        self.FILES.NEW.close()

#set of input/output files taken from cmd line and opened
class FileSet:
    def __init__(self, og, new):
        self.OG = open(og,"r", encoding="UTF-8")
        self.NEW = open(new,"w+", encoding="UTF-8") #read and delete all to overwrite
        self.ERROR_LOG_NAME = self._get_error_log_name(new) #replace period in file name with _

    def _get_error_log_name(self, file_name): #produces error log name for file (without . from file name)
        temp = file_name.replace("./", "")
        temp = temp.replace(".", "_")
        return f"./{temp}_error_log.err"
    #these are used to read/write files and reset file pointer at same time:
    def read_og(self):
        og_content = self.OG.readlines()
        self.OG.seek(0)
        return og_content
    def read_new(self):
        new_content = self.NEW.readlines()
        self.NEW.seek(0)
        return new_content
    def write_new(self, lines):
        self.NEW.truncate()
        self.NEW.writelines(lines)
        self.NEW.seek(0)


def main(argv):
    #reading arguments and checking them for errors
    argc = 1
    try:
        opts, args = getopt.getopt(argv,"hi:o:",["input=","output="])
    except getopt.GetoptError:
        print("ERROR: Syntax Incorrect. Please use: parser.py -i|--input <existing input_file> -o|--output <output_file>")
        sys.exit(3)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            print("Help (usage): parser.py -i|--input <existing input_file> -o|--output <output_file>")
            sys.exit()
        elif opt in ("-i", "--input"):
            input_file = arg
            argc += 1
            if not os.path.isfile(input_file):
                print("ERROR: Input File path does not exist.")
                sys.exit(4)
        elif opt in ("-o", "--output"):
            output_file = arg
            argc += 1
    if argc != 3:
        print("ERROR: Syntax Incorrect. Please use: parser.py -i|--input <existing input_file> -o|--output <output_file>")
        sys.exit(5)
    #create file correction object with instance globals and methods
    file_system = FileCorrector(input_file, output_file)

    print("Input File: " + input_file + "\n" + "Output File: " + output_file)
    print(f"Error log in: {file_system.FILES.ERROR_LOG_NAME}")

    #run correction function
    file_system.correct_file()

    file_system.close()


if __name__ == "__main__":
   main(sys.argv[1:])