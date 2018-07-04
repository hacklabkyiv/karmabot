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

0. Install `docker`
1. Clone the repo `git clone https://github.com/dethoter/karmabot $HOME/.karmabot`
2. `./docker_build.sh`
3. `./docker_run.sh`

This `Dockerfile` from repo contains setup for RaspberryPi.
You can modify **FROM** field in order to target your distro.


## Usage

1. Add a [Slack Bot](https://api.slack.com/bot-users) integration.
2. Invite `karmabot` to any existing channels and all future channels
3. Run `karmabot`. the following environment variables are supported:

| option                      | required? | description                              | default                          |
| --------------------------- | --------- | ---------------------------------------- | -------------------------------- |
| `BOT_LANG`                  | no        | options: en, ru                          | en                                    |
| `DB_URI`                    | **yes**   | path to database (may be any DB that sqlalchemy supports) | `sqlite:///karma.db` |
| `SLACK_BOT_TOKEN`           | **yes**   | slack RTM token                          |                                       |
| `INITIAL_USER_KARMA`        | no        | the default amount of user karma         | `0`                                   |
| `MAX_SHOT`                  | no        | the maximum amount of points that users can give/take at once | `5`              |
| `VOTE_TIMEOUT`              | no        | a time to wait until a voting closes     | `true`                                |
| `UPVOTE_EMOJI`              | no        | reactjis to use for upvotes.             | `+1`, `thumbsup`, `thumbsup_all`      |
| `DOWNVOTE_EMOJI`            | no        | reactjis to use for downvotes.           | `-1`, `thumbsdown`                    |
| `SELF_KARMA`                | no        | allow users to add/remove karma to themselves | `false`                          |
| `ADMINS`                    | no        | admins who can set karma to users        |                                       |
| `LOG_LEVEL`                 | no        | set log level                            | `INFO`                                |


### Testing

In order to test locally use:

```sh
$ pipenv install
$ env $(cat .env | xargs) pipenv run python ./karmabot.py
```


### Commands

All the commands should be sent into direct messages to **karmabot**.

| command   | arguments                       | description                             |
| --------- | ------------------------------- | --------------------------------------- |
| get       | `@username`                     | get a user's karma                      |
| set       | `@username <points>`            | set a user's karma to a specific number |
| config    |                                 | show config for this execution          |
| help      |                                 | show this message                       |


## License

see [./LICENSE](/LICENSE)
