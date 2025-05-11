Feature: Event Capacity

  Scenario: No limit set
    Given an event
      And the event registration limit is empty
    When visiting the event detail page
    Then the event does not show registrations remaining

  Scenario: Limit two, zero registration
    Given an event
      And the event registration limit is 2
      And the event has 0 registration
    When visiting the event detail page
    Then the event shows 0 registered
     And the event shows 2 registrations remaining

  Scenario: Limit two, one registration
    Given an event
      And the event registration limit is 2
      And the event has 1 registration
    When visiting the event detail page
    Then the event shows 1 registered
     And the event shows 1 registration remaining

  Scenario: Limit two, two registrations
    Given an event
      And the event registration limit is 2
      And the event has 2 registration
    When visiting the event detail page
    Then the event shows 2 registered
     And the event shows 0 registrations remaining

  Scenario: Limit two, three registrations
    Given an event
      And the event registration limit is 2
      And the event has 3 registration
    When visiting the event detail page
    Then the event shows 3 registered
     And the event shows 0 registrations remaining

  Scenario: External registration has no count
    Given an event
      And the event has external registration
    When visiting the event detail page
    Then the event does not show registrations remaining
     And the event does not show registrations