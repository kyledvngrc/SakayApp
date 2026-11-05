/*  Standalone tests for routes.pl (no database needed).
    Run from the repo root:
        swipl -g run_tests -t halt prolog/tests/test_routes.pl
*/

:- use_module('../routes').
:- use_module(library(plunit)).

%  Builds a network from a list of route(Code, Stops, bidirectional|oneway).
load(Routes) :-
    clear_legs,
    forall(member(route(R, Stops, Dir), Routes), add_route(R, Stops, Dir)).

add_route(R, Stops, Dir) :-
    forall(nextto(A, B, Stops),
           ( assertz(routes:leg(R, A, B)),
             ( Dir == bidirectional -> assertz(routes:leg(R, B, A)) ; true ) )).

%  Same shape as database/seed.sql: R01 1-2-3, R02 3-4-5, transfer at 3.
seed_network :-
    load([ route('R01', [1,2,3], bidirectional),
           route('R02', [3,4,5], bidirectional) ]).

all_plans(From, To, Max, Plans) :-
    findall(P, find_trip(From, To, Max, P, _), Plans).

:- begin_tests(seed, [setup(seed_network), cleanup(clear_legs)]).

test(direct_ride, [nondet]) :-
    find_trip(1, 3, Plan, 0),
    Plan == [ride('R01', 1, 3, [1,2,3])].

test(one_transfer, [true(Plans == [[ride('R01',1,3,[1,2,3]), ride('R02',3,5,[3,4,5])]])]) :-
    all_plans(1, 5, 2, Plans).

test(reverse_direction, [nondet]) :-
    find_trip(5, 1, Plan, 1),
    Plan == [ride('R02',5,3,[5,4,3]), ride('R01',3,1,[3,2,1])].

test(same_stop_fails, [fail]) :-
    find_trip(2, 2, _, _).

test(unknown_stop_fails, [fail]) :-
    find_trip(1, 99, _, _).

test(transfer_stop_detected, [nondet]) :-
    transfer_stop(3).

test(non_transfer_stop, [fail]) :-
    transfer_stop(2).

test(from_any_candidate, [nondet]) :-
    find_trips_from_any([1,2], [5], 2, [ride('R01', 2, 3, _)|_], 1).

:- end_tests(seed).

:- begin_tests(guards, [cleanup(clear_legs)]).

test(circular_route_terminates, [setup(load([route('C1', [10,11,12,13,10], oneway)])),
                                 true(Plans == [[ride('C1',10,12,[10,11,12])]])]) :-
    all_plans(10, 12, 2, Plans).

test(bidirectional_loop_gives_both_ways,
     [setup(load([route('C2', [10,11,12,13,10], bidirectional)])),
      true(Paths == [[10,11,12], [10,13,12]])]) :-
    all_plans(10, 12, 2, Plans),
    findall(S, member([ride(_,_,_,S)], Plans), Ss),
    msort(Ss, Paths).

test(oneway_wrong_direction_fails, [setup(load([route('O1', [30,31,32], oneway)])), fail]) :-
    find_trip(32, 30, _, _).

%  Regression: R01 only arrives at 3 (one-way), R02 leaves from 3.
test(oneway_transfer, [setup(load([ route('R01', [1,2,3], oneway),
                                    route('R02', [3,4,5], oneway) ])),
                       true(Plans == [[ride('R01',1,3,[1,2,3]), ride('R02',3,5,[3,4,5])]])]) :-
    all_plans(1, 5, 2, Plans).

test(transfer_cap_blocks, [setup(chain_network), fail]) :-
    find_trip(20, 24, 2, _, _).

test(transfer_cap_allows, [setup(chain_network), nondet]) :-
    find_trip(20, 24, 3, _, 3).

test(no_route_reused, [setup(load([ route('A', [1,2,3], bidirectional),
                                     route('B', [2,9], bidirectional) ]))]) :-
    forall(find_trip(1, 3, 2, Plan, _),
           ( findall(R, member(ride(R,_,_,_), Plan), Rs),
             sort(Rs, Unique), length(Rs, N), length(Unique, N) )).

:- end_tests(guards).

%  4 routes in a chain: reaching 24 from 20 needs 3 transfers.
chain_network :-
    load([ route('K1', [20,21], bidirectional),
           route('K2', [21,22], bidirectional),
           route('K3', [22,23], bidirectional),
           route('K4', [23,24], bidirectional) ]).
