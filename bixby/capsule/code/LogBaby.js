import http from 'http'
import config from 'config'
import secret from 'secret'

// Bixby가 받은 문장을 BabyMind 서버 /log 로 그대로 전달하고, 서버가 만든 문장을 읽어준다.
export default function ({ text }) {
  const res = http.postUrl(config.get('server.url') + '/log', { text: text, source: 'bixby' }, {
    format: 'json',
    passAsJson: true,
    headers: { 'X-API-Key': secret.get('babymind.token') },
  })
  return { speech: res.speech }
}
