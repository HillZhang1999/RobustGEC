import argparse
from collections import Counter
import errant
from errant.commands.parallel_to_m2 import convert_to_m2
from tqdm import tqdm
import pickle
import os

def remove_prefix(line):
    return " ".join(line.split()[1:])

def main():
    # Parse command line args
    args = parse_args()
    # Open files and split into chunks
    m2_chunk = [c for c in open(args.file).read().strip().split("\n\n") if c]
    if args.start is not None:
        m2_chunk = m2_chunk[args.start: args.end]
    
    if args.cache is not None:
        assert os.path.exists(args.cache)
        with open(args.cache, 'rb') as f:
            cache_dic = pickle.load(args.cache)

    # Store global corpus level best counts here
    original_dict = Counter({"tp":0, "fp":0, "fn":0})
    original_cats = {}
    best_dict = Counter({"tp":0, "fp":0, "fn":0})
    best_cats = {}
    worst_dict = Counter({"tp":0, "fp":0, "fn":0})
    worst_cats = {}
    
    annotator = errant.load("en")
    
    n = len(m2_chunk[0].split("\n")) // 3 - 1  # 标注答案数目
    orig_f = {}
    
    local_prf_list = []
    
    robust_case_num = 0   # 性能无波动的样本个数
    
    p_robust_case_num = 0  # pair-wise，得分和原始样本一致的扰动样本个数
    
    for sent_id, chunk in tqdm(enumerate(m2_chunk)):
        lines = chunk.split("\n")
        # Process original sentence
        orig_src_sent, orig_tgt_sent, orig_pred_sent = remove_prefix(lines[0]), remove_prefix(lines[1]), remove_prefix(lines[2])
        if args.cache and (orig_src_sent, orig_tgt_sent) in cache_dic.keys():
            orig_gold_edit = cache_dic[(orig_src_sent, orig_tgt_sent)]
        else:
            orig_gold_edit = convert_to_m2(annotator, orig_src_sent, orig_tgt_sent)
            cache_dic[(orig_src_sent, orig_tgt_sent)] = orig_gold_edit
        if args.cache and (orig_src_sent, orig_pred_sent) in cache_dic.keys():
            orig_pred_edit = convert_to_m2(annotator, orig_src_sent, orig_pred_sent)
            cache_dic[(orig_src_sent, orig_pred_sent)] = orig_pred_edit
        orig_hyp_edits, orig_ref_edits = simplify_edits(orig_pred_edit), simplify_edits(orig_gold_edit)
        orig_hyp_dict, orig_ref_dict = process_edits(orig_hyp_edits, args), process_edits(orig_ref_edits, args)
        
        count_dict, cat_dict = evaluate_edits(
            orig_hyp_dict, orig_ref_dict, original_dict, sent_id, orig_src_sent, args)
        
        _, _, local_f = computeFScore(count_dict["tp"], count_dict["fp"], count_dict["fn"], args.beta)
        orig_f[sent_id] = local_f
        original_dict += Counter(count_dict)
        original_cats = merge_dict(original_cats, cat_dict)
        
    print("Original Result:")
    print_results(original_dict, original_cats, args)
    
    for sent_id, chunk in tqdm(enumerate(m2_chunk)):
        # if sent_id not in wrong_case:
        #     continue
        lines = chunk.split("\n")
        
        cand_count_dict, cand_cat_dict = [], []
        
        for i in range(0, len(lines), 3):
            # Process original sentence
            adv_src_sent, adv_tgt_sent, adv_pred_sent = remove_prefix(lines[i]), remove_prefix(lines[i+1]), remove_prefix(lines[i+2])
            adv_gold_edit, adv_pred_edit = convert_to_m2(annotator, adv_src_sent, adv_tgt_sent), convert_to_m2(annotator, adv_src_sent, adv_pred_sent)
            # print(orig_gold_edit)
            adv_hyp_edits, adv_ref_edits = simplify_edits(adv_pred_edit), simplify_edits(adv_gold_edit)
            adv_hyp_dict, adv_ref_dict = process_edits(adv_hyp_edits, args), process_edits(adv_ref_edits, args)
            
            count_dict, cat_dict = evaluate_edits(
                adv_hyp_dict, adv_ref_dict, best_dict, sent_id, adv_src_sent, args)
            cand_count_dict.append(count_dict)
            cand_cat_dict.append(cat_dict)
            
        best_i, worst_i = 0, 0
        best_tp, best_fp, best_fn = cand_count_dict[0]["tp"], cand_count_dict[0]["fp"], cand_count_dict[0]["fn"]
        best_p, best_r, best_f = computeFScore(best_dict["tp"]+best_tp, best_dict["fp"]+best_fp, best_dict["fn"]+best_fn, args.beta)
        local_p, local_r, local_f = computeFScore(best_tp, best_fp, best_fn, args.beta)
        
        worst_tp, worst_fp, worst_fn = best_tp, best_fp, best_fn
        worst_p, worst_r, worst_f = computeFScore(worst_dict["tp"]+best_tp, worst_dict["fp"]+best_fp, worst_dict["fn"]+best_fn, args.beta)
        local_prf = [(local_p, local_r, local_f)]
        pair_wise_match = 0
        for i in range(1, len(cand_count_dict)):
            tp, fp, fn, cat_dict = cand_count_dict[i]["tp"], cand_count_dict[i]["fp"], cand_count_dict[i]["fn"], cand_cat_dict[i]
            local_p, local_r, local_f = computeFScore(tp, fp, fn, args.beta)
            local_prf.append((local_p, local_r, local_f))
            if local_f == local_prf[0][-1]:
                pair_wise_match += 1
            
            p, r, f = computeFScore(
                tp+best_dict["tp"], fp+best_dict["fp"], fn+best_dict["fn"], args.beta)
            if     (f > best_f) or \
                (f == best_f and tp > best_tp) or \
                (f == best_f and tp == best_tp and fp < best_fp) or \
                (f == best_f and tp == best_tp and fp == best_fp and fn < best_fn):
                best_tp, best_fp, best_fn, best_p, best_r, best_f = tp, fp, fn, p, r, f
                best_i = i 
                
            p, r, f = computeFScore(
                tp+worst_dict["tp"], fp+worst_dict["fp"], fn+worst_dict["fn"], args.beta)
            if     (f < worst_f) or \
                (f == worst_f and tp < worst_tp) or \
                (f == worst_f and tp == worst_tp and fp > worst_fp) or \
                (f == worst_f and tp == worst_tp and fp == worst_fp and fn > worst_fn):
                worst_tp, worst_fp, worst_fn, worst_p, worst_r, worst_f = tp, fp, fn, p, r, f
                worst_i = i
            
        best_dict += Counter(cand_count_dict[best_i])
        best_cats = merge_dict(best_cats, cand_cat_dict[best_i])
        
        worst_dict += Counter(cand_count_dict[worst_i])
        worst_cats = merge_dict(worst_cats, cand_cat_dict[worst_i])
        
        local_prf_list.append((local_prf, best_i, worst_i, (best_p, best_r, best_f), (worst_p, worst_r, worst_f)))
        
        if best_i == worst_i:
            robust_case_num += 1
            
        p_robust_case_num += pair_wise_match / (len(cand_count_dict) - 1)
            
    print(f"Best Result (Sample Num {n+1}):")
    print_results(best_dict, best_cats, args)
    
    print(f"Worst Result (Sample Num {n+1}):")
    print_results(worst_dict, worst_cats, args)
    
    print(f"CRS: {robust_case_num} ({robust_case_num / len(m2_chunk) * 100}%)")
    
    print(f"P-CRS: {p_robust_case_num} ({p_robust_case_num / len(m2_chunk) * 100}%)")
    
    if args.evallog:
        with open(args.evallog, "w", encoding="utf-8") as o:
            for sent_id, chunk in tqdm(enumerate(m2_chunk)):
                o.write(f"Sent ID: {sent_id}\n")
                lines = chunk.split("\n")
                for i in range(0, len(lines), 3):
                    o.write("\n".join(lines[i: i+3])+"\n")
                    local_prf = local_prf_list[sent_id][0]
                    local_p, local_r, local_f = local_prf[i//3]
                    o.write("Local Precision: {:.2f}, Local Recall: {:.2f}, Local F_{:.1f}: {:.2f}\n".format(local_p * 100, local_r * 100, args.beta, local_f * 100))
                best_i, worst_i = local_prf_list[sent_id][-4], local_prf_list[sent_id][-3]
                o.write(f"Selected Sample ID for higher F-value: {best_i}\n")
                best_p, best_r, best_f = local_prf_list[sent_id][-2]
                o.write("Highest P/R/F-value Till Now: {:.2f}/{:.2f}/{:.2f}\n".format(best_p * 100, best_r * 100, best_f * 100))
                o.write(f"Selected Sample ID for lower F-value: {worst_i}\n")
                worst_p, worst_r, worst_f = local_prf_list[sent_id][-1]
                o.write("Lowest P/R/F-value Till Now: {:.2f}/{:.2f}/{:.2f}\n".format(worst_p * 100, worst_r * 100, worst_f * 100))
                o.write("\n")
                
    if args.cache:
       with open(args.cache, 'wb') as f:
            pickle.dump(cache_dic, f)
            
# Parse command line args
def parse_args():
    parser = argparse.ArgumentParser(
        description="Calculate F-scores for error detection and/or correction.\n"
            "Flags let you evaluate at different levels of granularity.",
        formatter_class=argparse.RawTextHelpFormatter,
        usage="%(prog)s [options] -hyp HYP -ref REF")
    parser.add_argument(
        "-file",
        help="A hypothesis file.",
        required=True)
    parser.add_argument(
        "-cache",
        help="A cache file.",
        default=None)
    parser.add_argument(
        "-evallog",
        help="Eval Log.",
        default="")
    parser.add_argument(
        "-b",
        "--beta",
        help="Value of beta in F-score. (default: 0.5)",
        default=0.5,
        type=float)
    parser.add_argument(
        "-v",
        "--verbose",
        help="Print verbose output.",
        action="store_true")
    eval_type = parser.add_mutually_exclusive_group()
    eval_type.add_argument(
        "-dt",
        help="Evaluate Detection in terms of Tokens.",
        action="store_true")
    eval_type.add_argument(
        "-ds",
        help="Evaluate Detection in terms of Spans.",
        action="store_true")
    eval_type.add_argument(
        "-cs",
        help="Evaluate Correction in terms of Spans. (default)",
        action="store_true")
    eval_type.add_argument(
        "-cse",
        help="Evaluate Correction in terms of Spans and Error types.",
        action="store_true")
    parser.add_argument(
        "-single",
        help="Only evaluate single token edits; i.e. 0:1, 1:0 or 1:1",
        action="store_true")
    parser.add_argument(
        "-multi",
        help="Only evaluate multi token edits; i.e. 2+:n or n:2+",
        action="store_true")
    parser.add_argument(
        "-filt",
        help="Do not evaluate the specified error types.",
        nargs="+",
        default=[])
    parser.add_argument(
        "-cat",
        help="Show error category scores.\n"
            "1: Only show operation tier scores; e.g. R.\n"
            "2: Only show main tier scores; e.g. NOUN.\n"
            "3: Show all category scores; e.g. R:NOUN.",
        choices=[1, 2, 3],
        type=int)
    parser.add_argument(
        "-start",
        default=None,
        type=int)
    parser.add_argument(
        "-end",
        default=None,
        type=int)
    args = parser.parse_args()
    return args

# Input: An m2 format sentence with edits.
# Output: A list of lists. Each edit: [start, end, cat, cor, coder]
def simplify_edits(sent, cut_src=False):
    out_edits = []
    # Get the edit lines from an m2 block.
    if cut_src:
        edits = sent.split("\n")[1:]
    else:
        edits = sent.split("\n")
    # Loop through the edits
    for edit in edits:
        if edit:
            # Preprocessing
            edit = edit[2:].split("|||") # Ignore "A " then split.
            span = edit[0].split()
            start = int(span[0])
            end = int(span[1])
            cat = edit[1]
            cor = edit[2]
            coder = int(edit[-1])
            out_edit = [start, end, cat, cor, coder]
            out_edits.append(out_edit)
    return out_edits

# Input 1: A list of edits. Each edit: [start, end, cat, cor, coder]
# Input 2: Command line args
# Output: A dict; key is coder, value is edit dict.
def process_edits(edits, args):
    coder_dict = {}
    # Add an explicit noop edit if there are no edits.
    if not edits: edits = [[-1, -1, "noop", "-NONE-", 0]]
    # Loop through the edits
    for edit in edits:
        # Name the edit elements for clarity
        start = edit[0]
        end = edit[1]
        cat = edit[2]
        cor = edit[3]
        coder = edit[4]
        # Add the coder to the coder_dict if necessary
        if coder not in coder_dict: coder_dict[coder] = {}

        # Optionally apply filters based on args
        # 1. UNK type edits are only useful for detection, not correction.
        if not args.dt and not args.ds and cat == "UNK": continue
        # 2. Only evaluate single token edits; i.e. 0:1, 1:0 or 1:1
        if args.single and (end-start >= 2 or len(cor.split()) >= 2): continue
        # 3. Only evaluate multi token edits; i.e. 2+:n or n:2+
        if args.multi and end-start < 2 and len(cor.split()) < 2: continue
        # 4. If there is a filter, ignore the specified error types
        if args.filt and cat in args.filt: continue

        # Token Based Detection
        if args.dt:
            # Preserve noop edits.
            if start == -1:
                if (start, start) in coder_dict[coder].keys():
                    coder_dict[coder][(start, start)].append(cat)
                else:
                    coder_dict[coder][(start, start)] = [cat]
            # Insertions defined as affecting the token on the right
            elif start == end and start >= 0:
                if (start, start+1) in coder_dict[coder].keys():
                    coder_dict[coder][(start, start+1)].append(cat)
                else:
                    coder_dict[coder][(start, start+1)] = [cat]
            # Edit spans are split for each token in the range.
            else:
                for tok_id in range(start, end):
                    if (tok_id, tok_id+1) in coder_dict[coder].keys():
                        coder_dict[coder][(tok_id, tok_id+1)].append(cat)
                    else:
                        coder_dict[coder][(tok_id, tok_id+1)] = [cat]

        # Span Based Detection
        elif args.ds:
            if (start, end) in coder_dict[coder].keys():
                coder_dict[coder][(start, end)].append(cat)
            else:
                coder_dict[coder][(start, end)] = [cat]

        # Span Based Correction
        else:
            # With error type classification
            if args.cse:
                if (start, end, cat, cor) in coder_dict[coder].keys():
                    coder_dict[coder][(start, end, cat, cor)].append(cat)
                else:
                    coder_dict[coder][(start, end, cat, cor)] = [cat]
            # Without error type classification
            else:
                if (start, end, cor) in coder_dict[coder].keys():
                    coder_dict[coder][(start, end, cor)].append(cat)
                else:
                    coder_dict[coder][(start, end, cor)] = [cat]
    return coder_dict

# Input 1: A hyp dict; key is coder_id, value is dict of processed hyp edits.
# Input 2: A ref dict; key is coder_id, value is dict of processed ref edits.
# Input 3: A dictionary of the best corpus level TP, FP and FN counts so far.
# Input 4: Sentence ID (for verbose output only)
# Input 5: Command line args
# Output 1: A dict of the best corpus level TP, FP and FN for the input sentence.
# Output 2: The corresponding error type dict for the above dict.
def evaluate_edits(hyp_dict, ref_dict, best, sent_id, original_sentence, args):
    # Verbose output: display the original sentence
    if args.verbose:
        print('{:-^40}'.format(""))
        print("Original sentence " + str(sent_id) + ": " + original_sentence)
    # Store the best sentence level scores and hyp+ref combination IDs
    # best_f is initialised as -1 cause 0 is a valid result.
    best_tp, best_fp, best_fn, best_f, best_hyp, best_ref = 0, 0, 0, -1, 0, 0
    best_cat = {}
    # Compare each hyp and ref combination
    for hyp_id in hyp_dict.keys():
        for ref_id in ref_dict.keys():
            # Get the local counts for the current combination.
            tp, fp, fn, cat_dict = compareEdits(hyp_dict[hyp_id], ref_dict[ref_id])
            # Compute the local sentence scores (for verbose output only)
            loc_p, loc_r, loc_f = computeFScore(tp, fp, fn, args.beta)
            # Compute the global sentence scores
            p, r, f = computeFScore(
                tp+best["tp"], fp+best["fp"], fn+best["fn"], args.beta)
            # Save the scores if they are better in terms of:
            # 1. Higher F-score
            # 2. Same F-score, higher TP
            # 3. Same F-score and TP, lower FP
            # 4. Same F-score, TP and FP, lower FN
            if     (f > best_f) or \
                (f == best_f and tp > best_tp) or \
                (f == best_f and tp == best_tp and fp < best_fp) or \
                (f == best_f and tp == best_tp and fp == best_fp and fn < best_fn):
                best_tp, best_fp, best_fn = tp, fp, fn
                best_f, best_hyp, best_ref = f, hyp_id, ref_id
                best_cat = cat_dict
            # Verbose output
            if args.verbose:
                # Prepare verbose output edits.
                hyp_verb = list(sorted(hyp_dict[hyp_id].keys()))
                ref_verb = list(sorted(ref_dict[ref_id].keys()))
                # add categories
                # hyp_dict[hyp_id] looks like (0, 1, "str")
                # hyp_dict[hyp_id][h] is a list, always length one, of the corresponding category
                hyp_verb = [h + (hyp_dict[hyp_id][h][0],) for h in hyp_verb]
                ref_verb = [r + (ref_dict[ref_id][r][0],) for r in ref_verb]
                # Ignore noop edits
                if not hyp_verb or hyp_verb[0][0] == -1: hyp_verb = []
                if not ref_verb or ref_verb[0][0] == -1: ref_verb = []
                # Print verbose info
                print('{:-^40}'.format(""))
                print("SENTENCE "+str(sent_id)+" - HYP "+str(hyp_id)+" - REF "+str(ref_id))
                print("HYPOTHESIS EDITS :", hyp_verb)
                print("REFERENCE EDITS  :", ref_verb)
                print("Local TP/FP/FN   :", str(tp), str(fp), str(fn))
                print("Local P/R/F"+str(args.beta)+"  :", str(loc_p), str(loc_r), str(loc_f))
                print("Global TP/FP/FN  :", str(tp+best["tp"]), str(fp+best["fp"]), str(fn+best["fn"]))
                print("Global P/R/F"+str(args.beta)+"  :", str(p), str(r), str(f))
    # Verbose output: display the best hyp+ref combination
    if args.verbose:
        print('{:-^40}'.format(""))
        print("^^ HYP "+str(best_hyp)+", REF "+str(best_ref)+" chosen for sentence "+str(sent_id))
        print("Local results:")
        header = ["Category", "TP", "FP", "FN"]
        body = [[k, *v] for k, v in best_cat.items()]
        print_table([header] + body)
    # Save the best TP, FP and FNs as a dict, and return this and the best_cat dict
    best_dict = {"tp":best_tp, "fp":best_fp, "fn":best_fn}
    return best_dict, best_cat

# Input 1: A dictionary of hypothesis edits for a single system.
# Input 2: A dictionary of reference edits for a single annotator.
# Output 1-3: The TP, FP and FN for the hyp vs the given ref annotator.
# Output 4: A dictionary of the error type counts.
def compareEdits(hyp_edits, ref_edits):
    tp = 0    # True Positives
    fp = 0    # False Positives
    fn = 0    # False Negatives
    cat_dict = {} # {cat: [tp, fp, fn], ...}

    for h_edit, h_cats in hyp_edits.items():
        # noop hyp edits cannot be TP or FP
        if h_cats[0] == "noop": continue
        # TRUE POSITIVES
        if h_edit in ref_edits.keys():
            # On occasion, multiple tokens at same span.
            for h_cat in ref_edits[h_edit]: # Use ref dict for TP
                tp += 1
                # Each dict value [TP, FP, FN]
                if h_cat in cat_dict.keys():
                    cat_dict[h_cat][0] += 1
                else:
                    cat_dict[h_cat] = [1, 0, 0]
        # FALSE POSITIVES
        else:
            # On occasion, multiple tokens at same span.
            for h_cat in h_cats:
                fp += 1
                # Each dict value [TP, FP, FN]
                if h_cat in cat_dict.keys():
                    cat_dict[h_cat][1] += 1
                else:
                    cat_dict[h_cat] = [0, 1, 0]
    for r_edit, r_cats in ref_edits.items():
        # noop ref edits cannot be FN
        if r_cats[0] == "noop": continue
        # FALSE NEGATIVES
        if r_edit not in hyp_edits.keys():
            # On occasion, multiple tokens at same span.
            for r_cat in r_cats:
                fn += 1
                # Each dict value [TP, FP, FN]
                if r_cat in cat_dict.keys():
                    cat_dict[r_cat][2] += 1
                else:
                    cat_dict[r_cat] = [0, 0, 1]
    return tp, fp, fn, cat_dict

# Input 1-3: True positives, false positives, false negatives
# Input 4: Value of beta in F-score.
# Output 1-3: Precision, Recall and F-score rounded to 4dp.
def computeFScore(tp, fp, fn, beta):
    p = float(tp)/(tp+fp) if fp else 1.0
    r = float(tp)/(tp+fn) if fn else 1.0
    f = float((1+(beta**2))*p*r)/(((beta**2)*p)+r) if p+r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)

# Input 1-2: Two error category dicts. Key is cat, value is list of TP, FP, FN.
# Output: The dictionaries combined with cumulative TP, FP, FN.
def merge_dict(dict1, dict2):
    for cat, stats in dict2.items():
        if cat in dict1.keys():
            dict1[cat] = [x+y for x, y in zip(dict1[cat], stats)]
        else:
            dict1[cat] = stats
    return dict1

# Input 1: A dict; key is error cat, value is counts for [tp, fp, fn]
# Input 2: Integer value denoting level of error category granularity.
# 1: Operation tier; e.g. M, R, U.  2: Main tier; e.g. NOUN, VERB  3: Everything.
# Output: A dictionary of category TP, FP and FN based on Input 2.
def processCategories(cat_dict, setting):
    # Otherwise, do some processing.
    proc_cat_dict = {}
    for cat, cnt in cat_dict.items():
        if cat == "UNK":
            proc_cat_dict[cat] = cnt
            continue
        # M, U, R or UNK combined only.
        if setting == 1:
            if cat[0] in proc_cat_dict.keys():
                proc_cat_dict[cat[0]] = [x+y for x, y in zip(proc_cat_dict[cat[0]], cnt)]
            else:
                proc_cat_dict[cat[0]] = cnt
        # Everything without M, U or R.
        elif setting == 2:
            if cat[2:] in proc_cat_dict.keys():
                proc_cat_dict[cat[2:]] = [x+y for x, y in zip(proc_cat_dict[cat[2:]], cnt)]
            else:
                proc_cat_dict[cat[2:]] = cnt
        # All error category combinations
        else:
            return cat_dict
    return proc_cat_dict

# Input 1: A dict of global best TP, FP and FNs
# Input 2: A dict of error types and counts for those TP, FP and FNs
# Input 3: Command line args
def print_results(best, best_cats, args):
    # Prepare output title.
    if args.dt: title = " Token-Based Detection "
    elif args.ds: title = " Span-Based Detection "
    elif args.cse: title = " Span-Based Correction + Classification "
    else: title = " Span-Based Correction "

    # Category Scores
    if args.cat:
        best_cats = processCategories(best_cats, args.cat)
        print("")
        print('{:=^66}'.format(title))
        print("Category".ljust(14), "TP".ljust(8), "FP".ljust(8), "FN".ljust(8),
            "P".ljust(8), "R".ljust(8), "F"+str(args.beta))
        for cat, cnts in sorted(best_cats.items()):
            cat_p, cat_r, cat_f = computeFScore(cnts[0], cnts[1], cnts[2], args.beta)
            print(cat.ljust(14), str(cnts[0]).ljust(8), str(cnts[1]).ljust(8),
                str(cnts[2]).ljust(8), str(cat_p).ljust(8), str(cat_r).ljust(8), cat_f)

    # Print the overall results.
    print("")
    print('{:=^46}'.format(title))
    print("\t".join(["TP", "FP", "FN", "Prec", "Rec", "F"+str(args.beta)]))
    print("\t".join(map(str, [best["tp"], best["fp"],
        best["fn"]]+[res * 100 for res in list(computeFScore(best["tp"], best["fp"], best["fn"], args.beta))])))
    print('{:=^46}'.format(""))
    print("")

def print_table(table):
    longest_cols = [
        (max([len(str(row[i])) for row in table]) + 3)
        for i in range(len(table[0]))
    ]
    row_format = "".join(["{:>" + str(longest_col) + "}" for longest_col in longest_cols])
    for row in table:
        print(row_format.format(*row))

if __name__ == "__main__":
    # Run the program
    main()
