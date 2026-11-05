/*  SakayApp route finder                                   (LOGIC PARADIGM)

    Jeepneys pick up and drop off anywhere along their route, so there are no
    fixed stops. A position on a route is the distance in metres along the
    route's drawn line, measured from where the line starts.

    Facts (asserted by the back-end at startup and after every admin edit)
    -----
    route(Code, Kind, LengthM)
        Kind is one of:
          both    runs both ways on the same streets
          oneway  runs only in the direction the line was drawn
          loop    one way, and the line ends where it starts (wraps around)

    link(FromRoute, FromPos, ToRoute, ToPos, WalkM)
        A commuter can get off FromRoute at FromPos and catch ToRoute at
        ToPos after walking WalkM metres (0 where the lines cross). Found by
        the back-end from the geometry of the lines.

    Query
    -----
    best_trips(+Starts, +Goals, +MaxTransfers, -Plans)
        Starts: list of s(Route, Pos, WalkM), places to catch a route near
                the origin, with the walk to get there.
        Goals:  list of g(Route, Pos, WalkM), places to get off near the
                destination, with the walk from there.
        Plans:  one plan per sequence of routes (the cheapest one), each a
                list of leg(Route, BoardPos, AlightPos, RideM, WalkToNextM).

    Guards
    ------
    - A trip never rides the same route twice.
    - The number of transfers is capped (default 2).
    - A ride only goes the way the route runs (oneway, loop).
*/

:- module(routes, [
    route/3,
    link/5,
    clear_network/0,
    ride/4,
    trip/6,
    find_trip/5,
    plan_cost/4,
    best_trips/4,
    best_trip_rows/4
]).

:- dynamic route/3, link/5.

default_max_transfers(2).

%   Walking counts this many times more than riding when choosing between
%   plans that use the same routes.
walk_weight(3).

%!  clear_network is det.
%   Remove all route/3 and link/5 facts (before reloading from the database).
clear_network :-
    retractall(route(_, _, _)),
    retractall(link(_, _, _, _, _)).

%!  ride(+Route, +From, +To, -RideM) is semidet.
%   Riding Route from position From to To is possible and covers RideM metres.
ride(Route, From, To, RideM) :-
    route(Route, Kind, Length),
    ride_distance(Kind, Length, From, To, RideM),
    RideM > 0.

ride_distance(both,   _,      From, To, M) :- M is abs(To - From).
ride_distance(oneway, _,      From, To, M) :- To > From, M is To - From.
ride_distance(loop,   Length, From, To, M) :- M is (To - From + Length) mod Length.

%!  trip(+Route, +Pos, +Goals, +MaxTransfers, +UsedRoutes, -Plan) is nondet.
%   Riding Route from Pos, either get off near the destination...
trip(Route, Pos, Goals, _, _, [leg(Route, Pos, Goal, M, 0)]) :-
    member(g(Route, Goal, _), Goals),
    ride(Route, Pos, Goal, M).
%   ...or get off at a link and continue on a route not used yet.
trip(Route, Pos, Goals, Max, Used, [leg(Route, Pos, Off, M, Walk)|Rest]) :-
    Max > 0,
    link(Route, Off, Next, On, Walk),
    \+ memberchk(Next, Used),
    ride(Route, Pos, Off, M),
    Max1 is Max - 1,
    trip(Next, On, Goals, Max1, [Next|Used], Rest).

%!  find_trip(+Starts, +Goals, +MaxTransfers, -Plan, -Transfers) is nondet.
%   Backtracking yields every valid plan from any start to any goal.
find_trip(Starts, Goals, Max, Plan, Transfers) :-
    member(s(Route, Pos, _), Starts),
    trip(Route, Pos, Goals, Max, [Route], Plan),
    length(Plan, N),
    Transfers is N - 1.

%!  plan_cost(+Plan, +Starts, +Goals, -Cost) is det.
%   Ride metres plus weighted walking (to the first route, between routes
%   and from the last route).
plan_cost(Plan, Starts, Goals, Cost) :-
    Plan = [leg(R0, P0, _, _, _)|_],
    last(Plan, leg(RN, _, PN, _, _)),
    memberchk(s(R0, P0, WalkIn), Starts),
    memberchk(g(RN, PN, WalkOut), Goals),
    foldl(add_leg, Plan, 0-0, Ride-Between),
    walk_weight(K),
    Cost is Ride + K * (WalkIn + Between + WalkOut).

add_leg(leg(_, _, _, M, W), Ride0-Walk0, Ride-Walk) :-
    Ride is Ride0 + M,
    Walk is Walk0 + W.

plan_routes(Plan, Routes) :-
    findall(R, member(leg(R, _, _, _, _), Plan), Routes).

%!  best_trips(+Starts, +Goals, +MaxTransfers, -Plans) is det.
%   The cheapest plan for each distinct sequence of routes. Many plans differ
%   only in where exactly the commuter boards or transfers; keep the best.
best_trips(Starts, Goals, Max, Plans) :-
    findall(Routes-(Cost-Plan),
            ( find_trip(Starts, Goals, Max, Plan, _),
              plan_cost(Plan, Starts, Goals, Cost),
              plan_routes(Plan, Routes) ),
            Pairs),
    keysort(Pairs, Sorted),
    group_pairs_by_key(Sorted, Groups),
    findall(Plan, ( member(_-Candidates, Groups),
                    min_member(_-Plan, Candidates) ),
            Plans).

%!  best_trip_rows(+Starts, +Goals, +MaxTransfers, -Rows) is det.
%   Same as best_trips/4, but each leg is a plain list
%   [Route, BoardPos, AlightPos, RideM, WalkToNextM] so the Python bridge can
%   read it reliably.
best_trip_rows(Starts, Goals, Max, Rows) :-
    best_trips(Starts, Goals, Max, Plans),
    maplist(maplist(leg_row), Plans, Rows).

leg_row(leg(R, A, B, M, W), [R, A, B, M, W]).
