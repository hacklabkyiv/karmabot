��          |      �          	   !     +     1  
   @     K     Y  
   f     q          �     �  d  �  $       :     V  �   m  �   1     �     �      �       3     7   I                                              	      
       cmd_error hello max_diff_error new_voting parsing_error report_karma robo_error strange_error time voting_result_nothing voting_result_success Project-Id-Version: PROJECT VERSION
Report-Msgid-Bugs-To: EMAIL@ADDRESS
PO-Revision-Date: 2019-11-03 22:46+0200
Last-Translator: FULL NAME <EMAIL@ADDRESS>
Language: en
Language-Team: en <LL@li.org>
Plural-Forms: nplurals=2; plural=(n != 1)
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
Generated-By: Babel 2.7.0
 One does not simply handle a command Hi! I'm *karmabot*. You can do:
- In any public channel
    `@karmabot @username +++ blah blah`
    If the most of you agree, the username will get a karma. Nothing will happen in any other case.

- Slack slash commands:
    - `/karmabot get @username` - get karma value for `username`
    - `/karmabot set @username <KARMA>` - set karma value for `username`
    - `/karmabot digest` - show users' karma in descending order (zero karma is skipped)
    - `/karmabot pending` - list pending votings
    - `/karmabot help` - show this message Max change is {} karma {} *A new voting for {:+d} karma for user @{}*
 You can vote using emoji for that or initial message.
 _FOR:_ {}
 _AGAINST_: {}
 Other emoji will be ignored. The voting will be *{}* long from now Сould not calculate what the fuck one has typed there {}
A request for karma change should be like `@karmabot @username +++ blah blah` @{}: {} karma Robots can also be offended {} This, at least, looks strange {} w d h min sec {} *The voting is finished*
@{} receives nothing {} {} *The voting is finished*
@{} receives {:+d} karma {} 