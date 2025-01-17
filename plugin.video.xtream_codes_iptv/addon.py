import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import parse_qsl, urlencode
import json

# Récupération des paramètres de l'addon
addon = xbmcaddon.Addon()
__url__ = sys.argv[0]
__handle__ = int(sys.argv[1])
server_url = addon.getSetting('server_url')
username = addon.getSetting('username')
password = addon.getSetting('password')

def build_url(query):
    """
    Construire une URL compatible avec Kodi avec les paramètres donnés.
    """
    return __url__ + '?' + urlencode(query)

def fetch_data(endpoint):
    """
    Récupérer les données de l'API Xtream Codes en utilisant urllib.
    """
    try:
        url = f"{server_url}/player_api.php?username={username}&password={password}&{endpoint}"
        with urlopen(url) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except HTTPError as e:
        xbmcgui.Dialog().notification("Xtream Codes IPTV", f"Erreur HTTP : {e.code}", xbmcgui.NOTIFICATION_ERROR, 5000)
    except URLError as e:
        xbmcgui.Dialog().notification("Xtream Codes IPTV", f"Erreur de connexion : {e.reason}", xbmcgui.NOTIFICATION_ERROR, 5000)
    except Exception as e:
        xbmcgui.Dialog().notification("Xtream Codes IPTV", f"Erreur : {e}", xbmcgui.NOTIFICATION_ERROR, 5000)
    return []

def show_main_menu():
    """
    Afficher le menu principal avec trois options : Live, VOD, et TVSHOWS.
    """
    # Option Live
    live_item = xbmcgui.ListItem(label="Live")
    live_url = build_url({'action': 'list_live_categories'})
    xbmcplugin.addDirectoryItem(handle=__handle__, url=live_url, listitem=live_item, isFolder=True)

    # Option VOD
    vod_item = xbmcgui.ListItem(label="VOD")
    vod_url = build_url({'action': 'list_vod_categories'})
    xbmcplugin.addDirectoryItem(handle=__handle__, url=vod_url, listitem=vod_item, isFolder=True)

    # Option TVSHOWS
    tvshows_item = xbmcgui.ListItem(label="TVSHOWS")
    tvshows_url = build_url({'action': 'list_series_categories'})
    xbmcplugin.addDirectoryItem(handle=__handle__, url=tvshows_url, listitem=tvshows_item, isFolder=True)

    xbmcplugin.endOfDirectory(__handle__)

# ================================
#           LIVE
# ================================
def show_live_categories():
    """
    Afficher les catégories Live.
    """
    categories = fetch_data('action=get_live_categories')
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['category_name'])
        url = build_url({'action': 'list_live_channels', 'category_id': category['category_id']})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(__handle__)

def show_live_channels(category_id):
    """
    Afficher les chaînes d'une catégorie Live spécifique.
    """
    channels = fetch_data(f"action=get_live_streams&category_id={category_id}")
    for channel in channels:
        list_item = xbmcgui.ListItem(label=channel['name'])
        list_item.setInfo('live', {'title': channel['name']})
        list_item.setArt({'thumb': channel.get('stream_icon', ''), 'poster': channel.get('stream_icon', '')})
        list_item.setProperty('IsPlayable', 'true')
        url = build_url({'action': 'play_channel', 'stream_url': f"{server_url}/live/{username}/{password}/{channel['stream_id']}.ts"} )
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=False)
    xbmcplugin.endOfDirectory(__handle__)

def play_channel(stream_url):
    """
    Lire une chaîne Live.
    """
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(__handle__, True, list_item)

# ================================
#           VOD
# ================================
def show_vod_categories():
    """
    Afficher les catégories VOD.
    """
    categories = fetch_data("action=get_vod_categories")
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['category_name'])
        url = build_url({'action': 'list_movies', 'category_id': category['category_id']})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(__handle__)

def show_movies(category_id):
    """
    Afficher les films d'une catégorie spécifique.
    """
    movies = fetch_data(f"action=get_vod_streams&category_id={category_id}")
    for movie in movies:
        list_item = xbmcgui.ListItem(label=movie['name'])
        list_item.setInfo('video', {'title': movie['name'], 'plot': movie.get('plot', 'Aucun synopsis')})
        list_item.setArt({'thumb': movie.get('stream_icon', ''), 'poster': movie.get('stream_icon', '')})
        list_item.setProperty('IsPlayable', 'true')
        url = build_url({'action': 'play_movie', 'stream_url': f"{server_url}/movie/{username}/{password}/{movie['stream_id']}.{movie['container_extension']}"} )
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=False)
    xbmcplugin.endOfDirectory(__handle__)

def play_movie(stream_url):
    """
    Lire un film.
    """
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(__handle__, True, list_item)

# ================================
#           TVSHOWS
# ================================
def show_series_categories():
    """
    Afficher les catégories des séries.
    """
    categories = fetch_data("action=get_series_categories")
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['category_name'])
        url = build_url({'action': 'list_series', 'category_id': category['category_id']})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(__handle__)

def show_series(category_id):
    """
    Afficher les séries pour une catégorie donnée.
    """
    series = fetch_data(f"action=get_series&category_id={category_id}")
    for serie in series:
        list_item = xbmcgui.ListItem(label=serie['name'])
        list_item.setInfo('video', {'title': serie['name'], 'plot': serie.get('plot', 'Aucun synopsis')})
        list_item.setArt({'thumb': serie.get('cover', ''), 'poster': serie.get('cover', '')})
        url = build_url({'action': 'list_seasons', 'series_id': serie['series_id']})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(__handle__)

def show_seasons(series_id):
    """
    Afficher les saisons pour une série donnée.
    """
    series_info = fetch_data(f"action=get_series_info&series_id={series_id}")
    seasons = series_info.get('episodes', {})
    for season, episodes in seasons.items():
        list_item = xbmcgui.ListItem(label=f"Saison {season}")
        url = build_url({'action': 'list_episodes', 'series_id': series_id, 'season': season})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(__handle__)

def show_episodes(series_id, season):
    """
    Afficher les épisodes pour une saison donnée.
    """
    series_info = fetch_data(f"action=get_series_info&series_id={series_id}")
    episodes = series_info.get('episodes', {}).get(season, [])
    for episode in episodes:
        list_item = xbmcgui.ListItem(label=episode['title'])
        list_item.setArt({'thumb': episode.get('info', {}).get('movie_image', '')})
        list_item.setProperty('IsPlayable', 'true')
        stream_url = f"{server_url}/series/{username}/{password}/{episode['id']}.{episode['container_extension']}"
        url = build_url({'action': 'play_episode', 'stream_url': stream_url})
        xbmcplugin.addDirectoryItem(handle=__handle__, url=url, listitem=list_item, isFolder=False)
    xbmcplugin.endOfDirectory(__handle__)

def play_episode(stream_url):
    """
    Lire un épisode.
    """
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(__handle__, True, list_item)

# ================================
#           ROUTEUR
# ================================
def router(paramstring):
    """
    Router les actions en fonction des paramètres.
    """
    params = dict(parse_qsl(paramstring))
    action = params.get('action')

    if action is None:
        show_main_menu()
    elif action == 'list_live_categories':
        show_live_categories()
    elif action == 'list_live_channels':
        category_id = params.get('category_id')
        show_live_channels(category_id)
    elif action == 'play_channel':
        stream_url = params.get('stream_url')
        play_channel(stream_url)
    elif action == 'list_vod_categories':
        show_vod_categories()
    elif action == 'list_movies':
        category_id = params.get('category_id')
        show_movies(category_id)
    elif action == 'play_movie':
        stream_url = params.get('stream_url')
        play_movie(stream_url)
    elif action == 'list_series_categories':
        show_series_categories()
    elif action == 'list_series':
        category_id = params.get('category_id')
        show_series(category_id)
    elif action == 'list_seasons':
        series_id = params.get('series_id')
        show_seasons(series_id)
    elif action == 'list_episodes':
        series_id = params.get('series_id')
        season = params.get('season')
        show_episodes(series_id, season)
    elif action == 'play_episode':
        stream_url = params.get('stream_url')
        play_episode(stream_url)
if __name__ == "__main__":
    router(sys.argv[2][1:])
