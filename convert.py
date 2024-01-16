import sys

def combine_answer_with_parallel(output_file, para_file, eval_file, n=5):
    """prepare the data format for evaluation

    Args:
        output_file (_type_): model output file
        para_file (_type_): the parallel dataset file
        eval_file (_type_): the final file for evaluation
        n (int, optional): the number of perturbed samples. Defaults to 5.
    """
    chunks = open(para_file, "r", encoding="utf-8").read().split("\n\n")
    answers = open(output_file, "r", encoding="utf-8").readlines()
    answer_chunks = [answers[i: i+n+1] for i in range(0, len(answers), n+1)]
    with open(eval_file, "w", encoding="utf-8") as o:
        for chunk, answer_chunk in zip(chunks, answer_chunks):
            lines = chunk.split("\n")
            new_lines = lines[:2] + ["O-P " + answer_chunk[0].rstrip("\n")]
            for i in range(1, n+1):
                new_lines.extend(lines[i*2:i*2+2])
                try:
                    new_lines.append(f"A{i}-P " + answer_chunk[i].rstrip("\n"))
                except:
                    print(lines)
                    print(chunk)
                    print(answer_chunk)
            for i in range(len(new_lines)):
                line = new_lines[i]
                tokens = " ".join(line.split()[1:])
                prefix = line.split()[0]
                tokenized = " ".join([t.text for t in nlp(tokens)])
                new_lines[i] = prefix + " " + tokenized 
            o.write("\n".join(new_lines) + "\n\n")
            
if __name__ == "__main__":
    output_file = sys.argv[1]
    para_file = sys.argv[2]
    eval_file = sys.argv[3]
    combine_answer_with_parallel(output_file, para_file, eval_file)