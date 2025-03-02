from transformers import pipeline
import torch
import json
import argparse
import re
import evaluate
from evaluate import load 
from tqdm import tqdm
from rouge_score import rouge_scorer


"""
Function to clean text by removing excessive spaces and newlines
Could be combined in the future with the load json function?
"""
def clean_text(text):
    # replace newlines with spaces
    text = text.replace('\n', ' ')
    # replace multiple spaces with a single space 
    text = re.sub(' +', ' ', text)
    return text.strip()


#TODO 
#update this method to load and clean, combine with clean_text method?
def load_json_input(file_path):
    """
    Load and validate the JSON input file.

    :param file_path: Path to the JSON file
    :return: List of dictionaries containing 'instruction', 'input', and 'output'
    """
    try: 
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Validate that each object contains the required fields
        for obj in data:
            if not all(key in obj for key in ['instruction', 'input', 'output']):
                raise ValueError("Each object must contain 'instruction', 'input', and 'output' fields.")
        
            obj['instruction'] = clean_text(obj['instruction'])
            obj['input'] = clean_text(obj['input'])

        print("Loaded data:", data[0])
        
        return data

    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format.")
    except FileNotFoundError:
        raise ValueError(f"File not found: {file_path}")



'''
function for evaluating outputs against ground truth
'''
def evaluate(candidates, references):
    import evaluate
    rouge = evaluate.load('rouge')
 
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=False)
    # Initialize accumulators for scores
    total_scores = {
        'rouge1': {'precision': 0, 'recall': 0, 'fmeasure': 0},
        'rouge2': {'precision': 0, 'recall': 0, 'fmeasure': 0},
        'rougeL': {'precision': 0, 'recall': 0, 'fmeasure': 0}
    }
    count = len(candidates)
    #debugging
    #print(candidates)
    #print(references)

    #debugging
    # Check the type of the lists
    #print(f"Type of candidates: {type(candidates)}")
    #print(f"Type of references: {type(references)}")

    # Check the length of the lists
    #print(f"Number of candidates: {len(candidates)}")
    #print(f"Number of references: {len(references)}")

    # Check the type of each element in the lists
    #if candidates and references:  # Ensure lists are not empty
        #print(f"Type of first candidate: {type(candidates[0])}")
        #print(f"Type of first reference: {type(references[0])}")

    # Optionally, print the first few elements to inspect their content
    #print("First few candidates:", candidates[:3])
    #print("First few references:", references[:3])

    results = rouge.compute(predictions=candidates, references=references)
    
    # Iterate over each candidate and reference pair to get rouge score using python rouge_scorer
    for candidate, reference in zip(candidates, references):
        # Compute the scores for the current pair
        scores = scorer.score(reference, candidate)
        
        # Accumulate the scores
        for key in total_scores:
            total_scores[key]['precision'] += scores[key].precision
            total_scores[key]['recall'] += scores[key].recall
            total_scores[key]['fmeasure'] += scores[key].fmeasure
    
    # Calculate average scores
    average_scores = {
        key: {
            'precision': total['precision'] / count,
            'recall': total['recall'] / count,
            'fmeasure': total['fmeasure'] / count
        }
        for key, total in total_scores.items()
    }
    
    # Print the average scores
    print("Average ROUGE scores:")
    for key, score in average_scores.items():
        print(f"{key}: Precision: {score['precision']:.4f}, Recall: {score['recall']:.4f}, F1: {score['fmeasure']:.4f}")
    
    print(results)


def main():
    parser = argparse.ArgumentParser()
    
    #add arguments for hyperparameters as neccessary 
    parser.add_argument('--input', '-i', help="input file in json format", required=True)
    parser.add_argument('--temperature', type=float, default=0.4, help="Sampling temperature")
  
    #recommended default temperature varies from model to model-- may need adjusting
    
    #parser.add_argument('--topk', type=int, default=50, help="Top-k sampling")
    parser.add_argument('--topp', type=float, default=0.95, help="Top-p (nucleus) sampling")
    #TODO
    #add arg for model directory
    parser.add_argument('--model', '-m', help="model directory", required=True)

    args = parser.parse_args()

    data = load_json_input(args.input)

    #If using base model
    model_id = args.model

    """
    Inference steps: add initial outputs to file.  then re-prompt.  then add final output.  then evaluate
    by comparing the initial outputs to ground truth, and the final outputs to ground truth.

    need to figure out how to get all of these (initial output, final output, gold truth) in one place in order
    to compare.  
    """
    

  
    pipe = pipeline(
        "text-generation", 
        model=model_id, 
        model_kwargs={"torch_dtype": torch.bfloat16},
        device="cuda",
        )
    
    #Maybe this should be combined with load function so that the json file only needs to be
    #looped through once
    """
    loop through all inputs, and format as messages, feed to model, record outputs and references for evaluation 
    """
    all_assistant_responses = []
    all_references= []

    for entry in tqdm(data, desc="Processing entries"):
        
    
        #system = entry['instruction']
        system = "Given the following clinical note, list possible diagnoses that could account for the patient's symptons and conditions.  Aim to cover all relevant possibilities."
        user = entry['input']

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        
        #debugging
        #print(messages)

    
        terminators = [
            pipe.tokenizer.eos_token_id,
            pipe.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        ]

        # In the future, make hyperparameters = input args  e.g. temperature=(args.temperature)
        outputs = pipe(
            messages,
            max_new_tokens=512,
            eos_token_id=terminators,
            do_sample=True,
            temperature=args.temperature,
            top_p=args.topp,
        )

        assistant_response = outputs[0]["generated_text"][-1]["content"]
        all_assistant_responses.append(assistant_response)
        all_references.append(entry['output'])
        #debugging
        print(assistant_response)

    evaluate(all_assistant_responses, all_references)
    

    #TODO
    #add print to print the inference hyperparameters along with results
    #possibly add model details as well
    


if __name__ == "__main__":
    main()