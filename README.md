# rengabot
An AI-powered image manipulation game for Slack and Discord

## The Rules

Users who are allowlisted as admins can set (or reset) the starting image in a channel.
Users can then take turns telling Rengabot to make one change to the image by mentioning
the bot publicly in the channel. The change is made and the new image is posted to the
channel. This then becomes the image that the next change is applied to, and so on.

### Example

| Action| Result |
| :---: | :---: |
| */rengabot set-image is called and this image is uploaded* | ![starting image](docs/image1_256.png) |
| @rengabot give the man a mohawk | ![first change](docs/image2_256.png) |
  @rengabot make his glasses way too big for his face | ![second change](docs/image3_256.png) |

## How It Works

The bot has a websocket connection to Slack and/or Discord. When a request is made to
change the image, it goes through a two-phase process with the AI model. In the first phase,
it validates that the user's prompt is in accordance with the rules of the game (e.g. only
one change at a time). This validation step can be run against a cheaper model. If the
change is deemed valid, we pass it and the base image to an image generation model.

## Setup
Copy `sample-config.yaml` to `config.yaml` and change settings as appropriate.

### AI Model

Currently the only supported model is Gemini.

#### Gemini
You will need an API key. Go to [AI Studio](https://aistudio.google.com) and create an
API key. You can place this key in your config.yaml or the `GEMINI_API_KEY` environment
variable.

### Chat
#### Slack
- Install the app using the `slack-manifest.yaml` file following the instructions [here](https://docs.slack.dev/app-manifests/configuring-apps-with-app-manifests/)
- In `config.yaml` under `slack`:
  - Ensure `enabled` is `true`
  - Set the bot token and app token (or alternately set these with the `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` environment variables)
  - Under `admins` add the user IDs that are allowed to set/reset the base image

#### Discord
Discord does not use a manifest file. Configure the app in the Discord Developer Portal:
- Create an application and add a bot.
- Make sure to make this a private bot so people can't spend your money:
  - On the installation tab, set the install link to None
  - On the bot tab, make sure public bot is unchecked
- On the OAuth2 tab:
  - Scopes:
    - Check the `bot` and `applications.commands` options
  - Bot permissions:
    - Check the `Send messages`, `Attach files`, and `Use slash commands` options
- On the bot tab:
  - Enable the Message Content Intent (required so the bot can read mention prompts)
- Copy the generated URL into your browser to invite the bot to your server
- In `config.yaml` under `discord`:
  - Ensure 'enabled' is `true`
  - Set the bot token (or alternately set the `DISCORD_BOT_TOKEN` environment variable)
  - Under admins list the user IDs of the people allowed to set/reset the base image
  - Set your server ID under `guild_id` for changes to slash commands to show up faster (for developers)
