/*  SakayApp route finder                                   (LOGIC PARADIGM)

    Facts
    -----
    leg(RouteCode, FromStop, ToStop)
        One hop between consecutive stops on a route. The back-end asserts
        these at startup from the PostgreSQL view v_legs (reverse legs are
        already included for bidirectional routes). Route codes are atoms
        ('R01'); stop ids are integers.

    Main queries
    ------------
    find_trip(+From, +To, -Plan, -Transfers)
    find_trip(+From, +To, +MaxTransfers, -Plan, -Transfers)
    find_trips_from_any(+FromStops, +ToStops, +MaxTransfers, -Plan, -Transfers)

    Plan is a list of ride(Route, BoardStop, AlightStop, Stops), where Stops
    is the ordered list of stop ids ridden, board to alight inclusive.
    Backtracking yields every valid plan; Python ranks them.

    Guards
    ------
    - A single ride never revisits a stop, so circular routes terminate.
    - A trip never revisits a transfer stop and never reuses a route.
    - Transfers happen only at stops served by more than one route.
    - The number of transfers is capped (default 2).
*/

:- module(routes, [
    leg/3,
    clear_legs/0,
    ride/4,
    transfer_stop/1,
    find_trip/4,
    find_trip/5,
    find_trips_from_any/5
]).

:- dynamic leg/3.

default_max_transfers(2).

%!  clear_legs is det.
%   Remove all leg/3 facts (used before reloading from the database).
clear_legs :-
    retractall(leg(_, _, _)).

%!  ride(?Route, +From, ?To, -Stops) is nondet.
%   Ride Route from From to To without revisiting any stop.
ride(Route, From, To, Stops) :-
    ride_(Route, From, To, [From], Reversed),
    reverse(Reversed, Stops).

ride_(Route, From, To, Visited, [To|Visited]) :-
    leg(Route, From, To),
    \+ memberchk(To, Visited).
ride_(Route, From, To, Visited, Out) :-
    leg(Route, From, Next),
    Next \== To,
    \+ memberchk(Next, Visited),
    ride_(Route, Next, To, [Next|Visited], Out).

%!  transfer_stop(?Stop) is nondet.
%   Stop is served by at least two different routes.
transfer_stop(Stop) :-
    leg(R1, Stop, _),
    leg(R2, Stop, _),
    R1 \== R2.

%!  trip(+From, +To, +MaxTransfers, +VisitedStops, +UsedRoutes, -Plan)
%   Final ride straight to the destination...
trip(From, To, _, _, Used, [ride(R, From, To, Stops)]) :-
    ride(R, From, To, Stops),
    \+ memberchk(R, Used).
%   ...or ride to a transfer stop and continue on a different route.
trip(From, To, Max, Visited, Used, [ride(R, From, X, Stops)|Rest]) :-
    Max > 0,
    ride(R, From, X, Stops),
    \+ memberchk(R, Used),
    X \== To,
    \+ memberchk(X, Visited),
    once(transfer_stop(X)),
    Max1 is Max - 1,
    trip(X, To, Max1, [X|Visited], [R|Used], Rest).

find_trip(From, To, Plan, Transfers) :-
    default_max_transfers(Max),
    find_trip(From, To, Max, Plan, Transfers).

find_trip(From, To, Max, Plan, Transfers) :-
    From \== To,
    trip(From, To, Max, [From], [], Plan),
    length(Plan, N),
    Transfers is N - 1.

%!  find_trips_from_any(+FromStops, +ToStops, +Max, -Plan, -Transfers)
%   Try every (origin, destination) pair of candidate stops near the user.
find_trips_from_any(FromStops, ToStops, Max, Plan, Transfers) :-
    member(From, FromStops),
    member(To, ToStops),
    find_trip(From, To, Max, Plan, Transfers).
