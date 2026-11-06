FLOODLINE — 10 MIN SCRIPT
(▶ = do this on screen)

====================
1. INTRO  (~30 sec)
====================
▶ Top of the page. Globe and title.

Hi everyone, I'm Ishita Chakkalakkal.
I'm a software engineering student at FGCU,
and I'm presenting for our team, Risk it for the Qiskit.

Our project is called Floodline.

The short version:
it tells Key West which streets are going to flood,
and it tests whether a quantum computer can figure that out faster than a regular one.

====================
2. THE STORY  (~1 min 15 sec)
====================
Key West is a really hard place to predict flooding.

It doesn't flood from just one thing.
It floods from the tide, heavy rain, quick bursts of rain, rising sea levels, and groundwater coming up from below.
Often all at the same time.

That's called compound flooding.

And the city has real decisions to make.
Which streets will go under?
Which roads are worth raising?
And they need those answers before the water shows up.

▶ Scroll slowly into the Irma story.

Here's a real example.
In 2017, Hurricane Irma hit the Florida Keys as a Category 4.

▶ Keep scrolling.

At Key West, the water rose almost three feet above normal high tide.

▶ Keep scrolling to the 3D island.

This is Key West in 3D, built from real government elevation data.
As I scroll, you'll see the water rise through the official flood levels.

▶ Scroll through each level.

This is minor flooding.
This is moderate.
And this is major.

Notice the streets that go under first aren't always by the beach.
It's whatever sits lowest.

▶ Stop on "where Irma put the water."

And this is where Irma actually put the water.

====================
3. WHY THIS MATTERS  (~1 min 15 sec)
====================
▶ Click SAVINGS in the top bar.
▶ Pause on $13.5B.

So why does this matter?

Four recent hurricanes, Irma, Ian, Helene, and Milton,
led to 13.5 billion dollars in flood insurance claims in Florida alone.

And that's just flooding. Not wind, not anything else.

▶ Point at the table.

Some of these hit close to home for us.
Ian came right through Southwest Florida.
And during Helene, 12 people drowned in the storm surge in Pinellas County.

So predicting floods isn't just a math problem.
It's how cities and emergency managers decide what to do before a storm hits.

====================
4. THE TIME PROBLEM  (~1 min 30 sec)
====================
▶ Scroll to "Real flood models are black boxes."

Here's the catch.
Predicting floods takes a huge amount of computer time.

When a hurricane is coming,
NOAA runs about 630 storm-surge simulations for every single forecast update.
And they have about one hour to get it all out.

And one detailed storm-surge simulation can take 2,000 hours of computer time.

So the bottleneck isn't the science. It's time.

▶ Scroll to "What it could save."

This is where our project comes in.

We found that a quantum computer could do these studies with up to 3.3 times fewer simulation runs.

▶ Point at "Two days of warning."

Think about a hurricane with two days of warning.

A big flood study could take about 45 hours of computing.
That's almost the whole two days gone, just waiting on computers.

With our method, that same study could take about 13 and a half hours.

That's the difference between getting results after the storm is basically here,
and getting them with more than a day to spare.
That's time to evacuate people, move equipment, and close roads.

It would also save money.
Around 16 to 42 thousand dollars per study,
and up to 330 thousand for a really big one.

▶ Click "How we calculated this," then close it.

Now, to be honest,
this is on a future quantum computer, not one that exists today.
And every number here has its source and assumptions written out right on the site.

====================
5. THE TOOL  (~1 min)
====================
▶ Click TOOL in the top bar.
▶ Pause on 3 IN 4.

Now here's the part that works today, on a regular computer.

If you buy a house in Key West with a 30-year mortgage,
there's a 3 in 4 chance the sea reaches major flood level at least once.

That's based on 110 years of tide records.

▶ Point at the road table.

Floodline ranks which roads the city should raise first.

Number one is Flagler Avenue.
Its lowest point has a 99 percent chance of flooding in 2050.

Raising it one foot would cost about 7 to 17 and a half million dollars
for every year of flooding it prevents.

So instead of guessing, the city gets a ranked list backed by data.

====================
6. TONIGHT  (~45 sec)
====================
▶ Click TONIGHT in the top bar.

This part is live.

It pulls the real tide forecast and the real rain forecast for Key West, right now.
Then it shows which streets could flood at the next high tides.

▶ Point at the street list.

So someone living there could check this and decide whether to move their car tonight.

▶ Click "Inputs, method and limits."

It runs 45 slightly different versions of the forecast,
so it can tell you how sure it is, not just yes or no.

It's a research prototype, not an official warning.
But it shows what the tool can do.

====================
7. HOW THE QUANTUM PART WORKS  (~1 min)
====================
▶ Click RESULTS in the top bar.
▶ Pause on the big 4.3×.

Okay, so how does the quantum part actually work?

Normally, to figure out the chance a street floods,
you simulate thousands of possible years of weather,
and count how many of them flood the street.

That's called Monte Carlo.
It's basically like flipping a coin over and over to figure out the odds.

The problem is, it's slow.
To get twice as accurate, you need four times as many runs.

There's a quantum algorithm called quantum amplitude estimation
that can get the same answer with way fewer tries.

Instead of flipping coins one at a time,
it puts every possible scenario into the quantum computer at once,
and measures the answer from there.

We built it using IBM's Qiskit.

====================
8. THE RACE  (~1 min)
====================
▶ Scroll to the race. Click "Play the race."

This is a race running live in the browser.

On one side, regular Monte Carlo.
On the other, the quantum method.
Both are trying to get the same answer, the chance this street floods.

Watch the tries counter on each side.

The quantum side gets close to the right answer in way fewer tries.

▶ When it finishes, point at the "1 second" box.

Here's why that matters.
Imagine each try is a flood simulation that takes one second.

In our runs, Monte Carlo needed around 70 hours.
That misses a 6-hour forecast window completely.

The quantum method needed under 4 hours.
That fits inside a single forecast window.

Again, that's on a perfect quantum computer.
But that's the size of the speedup we're talking about.

====================
9. FAIR FIGHT  (~1 min)
====================
▶ Scroll to chart 1.

Now, beating regular Monte Carlo is kind of the easy win.

So we also tested against the smartest regular method we could find.

And honestly, on simple flood models, the regular computer still wins.
You can see that on the left side of this chart.

But real flood models aren't simple.
There's a lot we don't know for sure, like how deep the soil is,
or how well the storm drains work.

▶ Click "Method: what the 13 factors are," then close it.

When we added those unknowns,
up to 13 of them,
the quantum method needed 4.3 times fewer tries than the best regular method.

It breaks even around 7 unknowns,
and starts winning from 9 on.

So the messier and more realistic the problem gets,
the better quantum looks.

▶ Scroll to chart 2.

And real storm-surge models are black boxes,
where you can't see inside them.
In that setup, quantum needed up to 3.3 times fewer runs.
That's the number behind the time savings I showed earlier.

====================
10. REAL HARDWARE  (~45 sec)
====================
▶ Scroll to "It runs on a real quantum computer."

We didn't just simulate it.
We ran a small version on IBM's actual quantum computer, called ibm_fez.

You can see the up-and-down pattern the algorithm needs actually showing up on the real chip.

But today's quantum computers are noisy,
so the answer got a little off.
It said about 7.4 percent, when the real answer is 9.6.

▶ Scroll to "Where classical still wins."

So we're upfront about it.
This table lists every case where regular computers still win.
Today's quantum chips need to be about a million times cleaner to pull this off.

====================
11. VERDICT  (~30 sec)
====================
▶ Click VERDICT in the top bar.

So here's where we landed.

On the left is what we proved.
On the right is what we didn't.

▶ Click METHODS in the top bar.

And every assumption we made is written out here,
so anyone can check our work.

====================
12. CLOSE  (~20 sec)
====================
Right now, regular computers run this tool,
and it's already useful for Key West.

But we found exactly where quantum starts to win.
And when quantum computers are ready,
Floodline is ready for them.

Thank you!
I'm Ishita, for team Risk it for the Qiskit.

▶ STOP RECORDING.
