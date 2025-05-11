Feature: Event iCal feed

  Scenario: Can load iCal feed
    Given an event
    When visiting the event ical feed
    Then the event ical feed contains the event
