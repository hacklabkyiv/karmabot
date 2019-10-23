**karmabot** is a Slack bot that listens for and performs karma operations.

*The main difference from other bots is that this one is community oriented.
This means that no karma will be applied unless community react using emoji.*

## Syntax

- Initiate a karma voting by posting to public channels:
  - `@karmabot @username ++ for blah blah`
  - `@karmabot @username -- for blah blah`

  Number of `+` or `-` is limited to `MAX_SHOT` points (see the **Usage** section below).
  Upvote/downvote a user by adding reactjis to their message.

- Get/set a karma of specific user by posting a direct message to karmabot.

## Installation

### 🐳 Docker

Install `docker` and then:

```sh
$ git clone https://github.com/dethoter/karmabot && cd karmabot
$ cp config.yml.template config.yml
# docker build -t karmabot .
# docker run -d --name karmabot --restart=unless-stopped --network=host -it karmabot
```

This `Dockerfile` from repo contains setup for RaspberryPi.
You can modify **FROM** field in order to target your distro.

### 💻 Locally

```sh
$ cp config.yml.template config.yml
$ pipenv install
$ python3 ./app.py
```


## Usage

1. Add a [Slack Bot](https://api.slack.com/bot-users) integration
2. Invite `karmabot` to any existing channels and all future channels
3. Run `karmabot`

### 📆 Autoposting

Set a channel in `auto_post.channel` and a day of a month in `auto_post.day` and get a monthly digest.

### 🗄 Backup

DB backups after each closed voting if a backup provider is configured.
In order to configure it user shoud pass provider's token to `backup.dropbox` env variable.

_Providers:_
  - ✅ **Dropbox**
  - 🔜 **GDrive**

### 📋 Configuration

| option                      | required? | description                              | default                          |
| --------------------------- | --------- | ---------------------------------------- | -------------------------------- |
| `log_level`                 | no        | set log level                            | `INFO`                           |
| `bot.lang`                  | no        | options: en, ru                          | en                               |
| `bot.slack_token`           | **yes**   | slack RTM token                          |                                  |
| `bot.admins`                | no        | admins who can set karma to users        |                                  |
| `karma.initial_value`       | no        | the default amount of user karma         | `0`                              |
| `karma.max_shot`            | no        | the maximum amount of points that users can give/take at once | `5`         |
| `karma.vote_timeout`        | no        | a time to wait until a voting closes     | `true`                           |
| `karma.upvote_emoji`        | no        | reactjis to use for upvotes.             | `+1`, `thumbsup`, `thumbsup_all` |
| `karma.downvote_emoji`      | no        | reactjis to use for downvotes.           | `-1`, `thumbsdown`               |
| `karma.self_karma`          | no        | allow users to add/remove karma to themselves | `false`                     |
| `auto_post.channel`         | no        | channel to post digest to                |                                  |
| `auto_post.day`             | no        | a day when auto digest will be posted    | `1`                              |
| `db.type`                   | no        | type of database (may be any DB that sqlalchemy supports) | `postgresql`    |
| `db.user`                   | no        | user of database                         |                                  |
| `db.password`               | no        | password for database                    |                                  |
| `db.host`                   | no        | host of database                         | `127.0.0.1`                      |
| `db.port`                   | no        | port of database                         | `5432`                           |
| `db.name`                   | **yes**   | name of database                         | `karma`                          |


### 📖 Commands

All the commands should be sent into direct messages to **karmabot**.

| command   | arguments                       | description                             |
| --------- | ------------------------------- | --------------------------------------- |
| get       | `@username`                     | get a user's karma                      |
| set       | `@username <points>`            | set a user's karma to a specific number |
| digest    |                                 | show users' karma in descending order (zero karma is skipped)|
| pending   |                                 | show pending votings                    |
| config    |                                 | show config for this execution          |
| help      |                                 | show this message                       |


## License

see [./LICENSE](/LICENSE)
