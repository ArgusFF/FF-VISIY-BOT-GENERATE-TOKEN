import os
import json
import requests
from github import Github

def generate_token(uid, password):
    url = f"https://jwt-generator-chi.vercel.app/cloudgen_jwt_single?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0 and "token" in data[0]:
            return data[0]["token"]
        else:
            raise ValueError("Unexpected API response format")
    except requests.RequestException as e:
        print(f"Error generating token for uid {uid}: {e}")
        raise
    except (KeyError, IndexError, ValueError) as e:
        print(f"Error parsing API response for uid {uid}: {e}")
        raise

def main():
    try:
        g = Github(os.environ["GITHUB_TOKEN"])
        repo = g.get_repo(os.environ["GITHUB_REPOSITORY"])
        
        regions = ["cis"]  # Только CIS
        
        for region in regions:
            input_file = f"input_{region}.json"
            output_file = f"token_{region}.json"
            
            try:
                contents = repo.get_contents(input_file)
                input_data = json.loads(contents.decoded_content.decode('utf-8'))
                print(f"Loaded {len(input_data)} entries from {input_file}")
            except Exception as e:
                print(f"Error reading {input_file}: {e}")
                continue
            
            tokens = []
            for entry in input_data:
                try:
                    uid = entry["uid"]
                    password = entry["password"]
                    token = generate_token(uid, password)
                    tokens.append({"token": token})
                    print(f"Generated token for UID: {uid}")
                except Exception as e:
                    print(f"Error processing entry: {e}")
                    continue
            
            if tokens:
                try:
                    output_content = json.dumps(tokens, indent=2)
                    try:
                        output_contents = repo.get_contents(output_file)
                        sha = output_contents.sha
                    except:
                        sha = None
                    repo.update_file(output_file, f"Update tokens for {region}", output_content, sha)
                    print(f"Updated {output_file} with {len(tokens)} tokens")
                except Exception as e:
                    print(f"Error writing {output_file}: {e}")
            else:
                print(f"No tokens generated for {input_file}")
    except Exception as e:
        print(f"Workflow failed: {e}")
        raise

if __name__ == "__main__":
    main()
