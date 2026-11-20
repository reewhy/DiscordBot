import { DiscordSDK, patchUrlMappings } from '@discord/embedded-app-sdk'

const CLIENT_ID = import.meta.env.VITE_DISCORD_CLIENT_ID

// Dentro Discord l'URL contiene ?frame_id=...; nel browser normale no (modalità sviluppo).
export const isEmbedded = new URLSearchParams(window.location.search).has('frame_id')

// Dentro Discord ogni richiesta esterna deve passare dal proxy "/.proxy".
export const BASE = isEmbedded ? '/.proxy' : ''

export const thumbUrl = (videoId) =>
  `${isEmbedded ? '/.proxy/ytimg' : 'https://i.ytimg.com'}/vi/${videoId}/mqdefault.jpg`

export async function setupDiscord() {
  if (!isEmbedded) {
    const name = 'Ospite-' + Math.floor(Math.random() * 900 + 100)
    return { instanceId: 'dev-room', guildId: null, channelId: null, user: { id: name, username: name, avatar: null } }
  }

  // Le richieste verso YouTube (script del player, iframe) vanno riscritte sul proxy.
  patchUrlMappings([{ prefix: '/youtube', target: 'www.youtube.com' }], {
    patchSrcAttributes: true
  })

  const sdk = new DiscordSDK(CLIENT_ID)
  await sdk.ready()

  const { code } = await sdk.commands.authorize({
    client_id: CLIENT_ID,
    response_type: 'code',
    state: '',
    prompt: 'none',
    scope: ['identify']
  })

  const res = await fetch(`${BASE}/api/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  })
  if (!res.ok) throw new Error('Impossibile completare il login con Discord.')
  const { access_token } = await res.json()

  const auth = await sdk.commands.authenticate({ access_token })
  if (!auth) throw new Error('Autenticazione con Discord non riuscita.')

  const u = auth.user
  return {
    instanceId: sdk.instanceId,
    guildId: sdk.guildId,
    channelId: sdk.channelId,
    user: {
      id: u.id,
      username: u.global_name || u.username,
      avatar: u.avatar ? `https://cdn.discordapp.com/avatars/${u.id}/${u.avatar}.png?size=64` : null
    }
  }
}
