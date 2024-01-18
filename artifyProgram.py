import spotipy
import time
import colorsys
import io
from spotipy.oauth2 import SpotifyOAuth
from colorthief import ColorThief
from urllib.request import urlopen

from flask import Flask, request, url_for, session, redirect

# initializes Flask app
app = Flask(__name__)

# sets name of session cookie, random secret key to sign the cookie, and key for token info in the session dictionary
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = 'SECRET'
TOKEN_INFO = 'token_info'

# route to handle logging in
@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url() # creates a SpotifyOAuth instance and gets the authorization URL
    return redirect(auth_url) # redirects user to the authorization url

# route to handle redirect URI after user authorization
@app.route('/redirect')
def redirect_page():
    session.clear() # clears session 
    code = request.args.get('code') # gets the authorization code from the request parameters
    token_info = create_spotify_oauth().get_access_token(code) # exchanges the authorization code for an access token and refresh token
    session[TOKEN_INFO] = token_info # saves the token info in the session
    return redirect(url_for('artify', external = True)) # redirects the user to artify route

# route to save the Discover Weekly songs to a playlist
@app.route('/artify')
def artify():
    try:
        token_info = get_token() # gets token info from session
    except: # if token info is not found, redirect user back to login route
        print("User not logged in")
        return redirect('/')
    
    # creates a spotipy instance with token_info as the access token
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # gets user id
    user_id = sp.current_user()['id']

    # initializes old and new playlist ids
    find_playlist = "ENTER DESIRED PLAYLIST"
    non_artified_playlist_id = None
    artified_playlist_id = None

    # finds playlist in user playlists
    current_user_playlists = sp.current_user_playlists()['items']
    for playlist in current_user_playlists:
        if find_playlist == playlist['name']:
            non_artified_playlist_id = playlist['id']
        if find_playlist + " (Artified)" == playlist['name']:
            artified_playlist_id = playlist['id']
    
    # checks if non artified playlist (find playlist) is in user playlists
    if not non_artified_playlist_id:
        return find_playlist + " not in your library, make sure playlist has been added to your profile"

    # checks if artified playlist has not already been created, creates if it hasn't
    if not artified_playlist_id:
        new_playlist = sp.user_playlist_create(user_id, find_playlist + " (Artified)", True)
        artified_playlist_id = new_playlist['id']

    # creates dictionary of song uris and corresponding dominant color code of cover arts, sorted using set sorting
    non_artified_playlist = sp.playlist_items(non_artified_playlist_id, limit=100)
    song_uris_and_color_codes = {}

    #print("nonartified length:", len(non_artified_playlist['items']))
    for song in non_artified_playlist['items']:
        # finds the dominant color of song
        song_image_url = song['track']['album']['images'][0]['url']
        song_dominant_color_code = find_dominant_color(song_image_url)

        # finds the song's uri
        song_uri = song['track']['uri']

        # adds both as a key value pair to dictionary
        song_uris_and_color_codes[song_uri] = song_dominant_color_code

    # sorts song_uris_and_color_codes based on the color codes (key) using step sorting
    song_uris_and_color_codes_keys = list(song_uris_and_color_codes.keys())
    song_uris_and_color_codes_keys.sort(key=lambda rgb: colorsys.rgb_to_hsv(*rgb))

    # adds sorted song uris to artified playlist
    sorted_song_uris_and_color_codes = {i: song_uris_and_color_codes[i] for i in song_uris_and_color_codes_keys}
    sp.user_playlist_add_tracks(user_id, artified_playlist_id, list(sorted_song_uris_and_color_codes.values()), None)

    return("Artified!")


# Finds dominant color of image using ColorThief Library, returns color code
# *Dominant Color is the color that shows up in the image the most, much more useful in this program as opposed to average color, which would mix all colors in the image together
def find_dominant_color(source_url):
    fd = urlopen(source_url)
    source_html_element = io.BytesIO(fd.read())
    ct = ColorThief(source_html_element)
    dominant_color = ct.get_color(quality=1)
    return dominant_color


# function to get the token info from the session
def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info: # if token info not found, redirect user to login route
        redirect(url_for('login', external=False))
    
    # checks if token has expired
    now = int(time.time())

    is_expired = token_info['expires_at'] - now < 60

    # refreshes if necessary
    if (is_expired):
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info



def create_spotify_oauth():
    return SpotifyOAuth(client_id = 'CLIENT_ID',
                        client_secret = 'CLIENT_SECRET',
                        redirect_uri = url_for('redirect_page', _external= True),
                        scope = 'user-library-read playlist-modify-public playlist-modify-private'
    )

app.run(debug=True)