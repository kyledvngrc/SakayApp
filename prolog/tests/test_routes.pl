/*  Standalone tests for routes.pl (no database needed).
    Run from the repo root:
        swipl -g run_tests -t halt prolog/tests/test_routes.pl
*/

:- use_module('../routes').
:- use_module(library(plunit)).

load(Routes, Links) :-
    clear_network,
    forall(member(R, Routes), assertz(routes:R)),
    forall(member(L, Links), assertz(routes:L)).

%  A (both ways, 2 km) crosses B (both ways, 1.5 km) at A 1500 / B 300.
%  C (one way, 1 km) starts 80 m walk from B at 1200.
crossing_network :-
    load([ route('A', both, 2000), route('B', both, 1500), route('C', oneway, 1000) ],
         [ link('A', 1500, 'B', 300, 0),  link('B', 300, 'A', 1500, 0),
           link('B', 1200, 'C', 0, 80),   link('C', 0, 'B', 1200, 80) ]).

plans(Starts, Goals, Max, Plans) :-
    findall(P, find_trip(Starts, Goals, Max, P, _), Plans).

:- begin_tests(rides, [cleanup(clear_network)]).

test(both_ways, [setup(crossing_network), true(M1-M2 == 500-500)]) :-
    ride('A', 1000, 1500, M1),
    ride('A', 1500, 1000, M2).

test(oneway_forward_only, [setup(crossing_network), fail]) :-
    ride('C', 600, 100, _).

test(loop_wraps_around, [setup(load([route('L', loop, 3000)], [])), true(M == 700)]) :-
    ride('L', 2800, 500, M).

test(no_zero_length_ride, [setup(crossing_network), fail]) :-
    ride('A', 700, 700, _).

:- end_tests(rides).

:- begin_tests(trips, [setup(crossing_network), cleanup(clear_network)]).

test(direct, [true(Plans == [[leg('A', 100, 900, 800, 0)]])]) :-
    plans([s('A', 100, 50)], [g('A', 900, 20)], 2, Plans).

test(one_transfer_where_lines_cross,
     [true(Plans == [[leg('A', 100, 1500, 1400, 0), leg('B', 300, 1000, 700, 0)]])]) :-
    plans([s('A', 100, 50)], [g('B', 1000, 20)], 2, Plans).

test(two_transfers_with_walk, [nondet]) :-
    find_trip([s('A', 100, 50)], [g('C', 900, 20)], 2, Plan, 2),
    Plan == [leg('A', 100, 1500, 1400, 0), leg('B', 300, 1200, 900, 80), leg('C', 0, 900, 900, 0)].

test(transfer_cap, [fail]) :-
    find_trip([s('A', 100, 50)], [g('C', 900, 20)], 1, _, _).

test(oneway_wrong_direction, [fail]) :-
    find_trip([s('C', 900, 10)], [g('C', 100, 10)], 2, _, _).

test(never_reuses_a_route) :-
    forall(find_trip([s('A', 100, 0)], [g('A', 1900, 0)], 2, Plan, _),
           ( findall(R, member(leg(R, _, _, _, _), Plan), Rs),
             sort(Rs, Unique), length(Rs, N), length(Unique, N) )).

test(unknown_route, [true(Plans == [])]) :-
    plans([s('X', 0, 0)], [g('A', 900, 0)], 2, Plans).

:- end_tests(trips).

:- begin_tests(best, [setup(crossing_network), cleanup(clear_network)]).

%  Two places to catch A near the origin: the shorter ride wins.
test(cheapest_per_route_sequence, [true(Plans == [[leg('A', 600, 900, 300, 0)]])]) :-
    best_trips([s('A', 100, 0), s('A', 600, 100)], [g('A', 900, 0)], 2, Plans).

%  ...unless walking to it costs more (walking counts 3x).
test(walking_weighs_more, [true(Plans == [[leg('A', 100, 900, 800, 0)]])]) :-
    best_trips([s('A', 100, 0), s('A', 600, 200)], [g('A', 900, 0)], 2, Plans).

test(one_plan_per_sequence, [true(Seqs == [['A'], ['A', 'B']])]) :-
    best_trips([s('A', 100, 0)], [g('A', 1800, 0), g('B', 1000, 0)], 2, Plans),
    findall(Rs, ( member(P, Plans), findall(R, member(leg(R,_,_,_,_), P), Rs) ), Seqs0),
    msort(Seqs0, Seqs).

test(cost, [true(Cost == 1640)]) :-
    plan_cost([leg('A', 100, 1500, 1400, 0)], [s('A', 100, 50)], [g('A', 1500, 30)], Cost).

:- end_tests(best).
