import tweepy
import random
import sys
import time
import imp

TESTMODE=False

random_prefixes = ('totally','totes','absolutely','certainly','mostly','definitely','er','erm','um')

def load_python_config(filename):
    return imp.load_module('config',file(filename,'r'), '', ('.py','U',1))

class DiceRoller(object):
    def __init__(self):
        self.random = random.SystemRandom()

    def parse(self, s):
        tokens = s.upper().split('D')
        if len(tokens) != 2:
            raise ValueError('Incorrect number of tokens after split.')

        # this may also raise a ValueError
        nr = int(tokens[0])

        if (nr <= 0):
            raise ValueError('Number of dice must be greater than 0.')

        if (nr > 30):
            raise ValueError('Number of dice must be less than 30.')


        # this may raise a ValueError
        sides = int(tokens[1])
        if (sides <= 0):
            raise ValueError('Number of sides must be greater than 0.')

        if (sides > 100):
            raise ValueError('Number of sides must be less than 1000.')

        return nr, sides

    def roll(self, s):
        try:
            nr, sides = self.parse(s)
        except ValueError:
            return None, None

        total = 0
        rolls = []
        for i in range(nr):
            rolls.append(self.random.randint(1, sides))
            total += rolls[-1]

        return rolls,total

    def format(self, rolls, total):
        if len(rolls) > 1:
            return '+'.join([str(s) for s in rolls]) + '=' + str(total)
        else:
            return str(total)

    def choice(self, choices):
        return self.random.choice(choices)

class StateSaver(object):
    def __init__(self, filename, filter_func=int):
        self.filename = filename
        self.state = None
        self.filter_func = filter_func
        self.message = ''

    def get(self):
        if not (self.state):
            value = None
            sfile = None
            try:
                sfile = file(self.filename,'r')
                value = self.filter_func(sfile.read())
            except IOError:
                self.message = 'cannot read state file'
            except ValueError:
                self.message = 'filter failure?'
            except:
                self.message = 'other error'
            finally:
                if sfile:
                    sfile.close()
            self.state = value
        return self.state

    def put(self, value):
        sfile = file(self.filename,'w')
        self.state = value
        sfile.write(str(self.state))
        sfile.close()

if __name__ == '__main__':
    try:
        config = load_python_config(sys.argv[1])
    except:
        print "need config file as first argument."
        sys.exit(1)

    dice = DiceRoller()

    statefile = StateSaver(config.STATEFILENAME)

    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.secure = True
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_SECRET)
    api = tweepy.API(auth)

    print api.me().name
    print '-' * len(api.me().name)

    since = statefile.get()
    if not since:
        print statefile.message
        try:
            since = int(sys.argv[2])
        except:
            print "need a since number as second argument."
            sys.exit(1)

    while (True):
        queue = list()
        try:
            mentions = api.mentions_timeline(since_id=since, count=5, page=0)
        except tweepy.error.TweepError, inst:
            print "tweeter error: ",inst
            print "sleeping for 3m."
            time.sleep(config.ERRORDELAY)
            continue

        for mention in mentions:
            tokens = mention.text.split()
            for tok in tokens[1:]:
                tweet = None
                rolls, total = dice.roll(tok)
                if rolls is None:
                    corpus = None
                    if tok.upper() == 'Y/N':
                        corpus = ('Y','N')
                    elif tok.upper() == 'T/F':
                        corpus = ('T','F')
                    elif tok.upper() == 'TRUE/FALSE':
                        corpus = ('TRUE','FALSE')
                    elif tok.upper() == 'YES/NO':
                        corpus = ('YES','NO')
                    elif tok.upper() == 'EVEN/ODD':
                        corpus = ('EVEN','ODD')
                    if corpus:
                        # calculate 1 in 2 outcome
                        tweet = '@'+mention.author.screen_name+' '+dice.choice(random_prefixes)+' '+dice.choice(corpus)
                    else:
                        continue
                else:
                    tweet = '@'+mention.author.screen_name+' '+tok+': '+dice.format(rolls, total)

                queue.append((mention.id, tweet))
                break

        if queue:
            queue.sort(lambda x, y: cmp(x[0], y[0]))
            since = queue[-1][0]

            statefile.put(since)

            for tw in queue:
                print tw
                if not TESTMODE:
                    try:
                        api.update_status(tw[1], tw[0])
                    except tweepy.error.TweepError, inst:
                        print "error: ",inst
                time.sleep(config.TWEETDELAY)

            print "Done processing mentions. Sleeping for 60s."
        time.sleep(config.CYCLEDELAY)
