import instaloader
import browser_cookie3
from pathlib import Path

#template for restarting cookies thru safari browser, just change username 
#to the instagram username you want to use, then run this. You may need
#to grant full disk access to terminal. Then run this script through .venv
def main():
    username = 'x'
    L = instaloader.Instaloader()
    
    print("Extracting Instagram cookies from Safari...")
    try:
        # Fetch Safari cookies for instagram.com
        cookies = browser_cookie3.safari(domain_name='instagram.com')
        # Load them directly into instaloader's active requests session
        L.context._session.cookies.update(cookies)
        print("Cookies successfully extracted!")
    except Exception as e:
        print(f"Error loading cookies from Safari: {e}")
        print("Make sure you granted Full Disk Access to Terminal and are logged into Instagram in Safari.")
        return
        
    # Manually assign the username to the instaloader context
    L.context.username = username
    
    # Save the session file directly, bypassing all verification checks
    session_file = Path.home() / ".config" / "instaloader" / f"session-{username}"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        L.save_session_to_file(str(session_file))
        print(f"\n🎉 SUCCESS! Session file successfully created at:")
        print(f"   {session_file}\n")
        print("Now you can run this command to generate your base64 string:")
        print(f"   base64 -i ~/.config/instaloader/session-{username}")
    except Exception as e:
        print(f"Error saving session file: {e}")

if __name__ == "__main__":
    main()
