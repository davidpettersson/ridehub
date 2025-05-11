Feature: Event iCal feed

  Scenario: Registration close time is absolute
    Given an event
    When visiting the event detail page
    Then the event shows when registration closes
